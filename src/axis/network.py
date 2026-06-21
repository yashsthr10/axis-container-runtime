from __future__ import annotations

import ipaddress
import fcntl
import json
import os
import shlex
import subprocess
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterator

from .config import AxisConfig
from .ports import PortMapping
from .process import output, run


BRIDGE = "axis0"
SUBNET = ipaddress.ip_network("10.88.0.0/24")
GATEWAY = ipaddress.ip_address("10.88.0.1")
NETWORK_STATE = Path(".axis/networks/axis0.json")
NETWORK_LOCK = Path(".axis/locks/network-axis0.lock")


@dataclass(frozen=True)
class NetworkState:
    container_id: str
    bridge: str
    host_veth: str
    container_veth: str
    gateway_ip: str
    container_ip: str
    subnet: str
    ports: list[PortMapping]


def setup_network(container_id: str, pid: int, config: AxisConfig, rootfs: Path) -> NetworkState:
    ensure_bridge()
    container_ip = allocate_ip(container_id)
    suffix = container_id.replace("-", "")[-8:]
    host_veth = f"axh{suffix}"[:15]
    container_veth = f"axc{suffix}"[:15]

    _run_ok(["ip", "link", "delete", host_veth])
    run(["ip", "link", "add", host_veth, "type", "veth", "peer", "name", container_veth])
    failpoint("after-veth-create")
    run(["ip", "link", "set", host_veth, "master", BRIDGE])
    run(["ip", "link", "set", host_veth, "up"])
    run(["ip", "link", "set", container_veth, "netns", str(pid)])
    run(["nsenter", "-t", str(pid), "-n", "ip", "addr", "replace", f"{container_ip}/24", "dev", container_veth])
    run(["nsenter", "-t", str(pid), "-n", "ip", "link", "set", container_veth, "up"])
    run(["nsenter", "-t", str(pid), "-n", "ip", "link", "set", "lo", "up"])
    run(["nsenter", "-t", str(pid), "-n", "ip", "route", "replace", "default", "via", str(GATEWAY)])

    run(["sysctl", "-w", "net.ipv4.ip_forward=1"])
    outbound = default_interface()
    ensure_iptables(["iptables", "-t", "nat", "-A", "POSTROUTING", "-s", str(SUBNET), "-o", outbound, "-j", "MASQUERADE"])
    ensure_iptables(["iptables", "-A", "FORWARD", "-i", BRIDGE, "-o", outbound, "-j", "ACCEPT"])
    failpoint("after-iptables")
    ensure_iptables(
        [
            "iptables",
            "-A",
            "FORWARD",
            "-i",
            outbound,
            "-o",
            BRIDGE,
            "-m",
            "conntrack",
            "--ctstate",
            "RELATED,ESTABLISHED",
            "-j",
            "ACCEPT",
        ]
    )

    write_name_resolution(rootfs, config.name, str(container_ip))
    for mapping in config.ports:
        remove_published_port_rules(mapping)

    return NetworkState(
        container_id=container_id,
        bridge=BRIDGE,
        host_veth=host_veth,
        container_veth=container_veth,
        gateway_ip=str(GATEWAY),
        container_ip=str(container_ip),
        subnet=str(SUBNET),
        ports=config.ports,
    )


def ensure_bridge() -> None:
    if _run_ok(["ip", "link", "show", BRIDGE]) != 0:
        run(["ip", "link", "add", "name", BRIDGE, "type", "bridge"])
    run(["ip", "addr", "replace", f"{GATEWAY}/24", "dev", BRIDGE])
    run(["ip", "link", "set", BRIDGE, "up"])


def allocate_ip(container_id: str) -> ipaddress.IPv4Address:
    with network_lock():
        state = read_network_state()
        allocations = state.setdefault("allocations", {})
        if container_id in allocations:
            return ipaddress.ip_address(allocations[container_id])

        used = {ipaddress.ip_address(value) for value in allocations.values()}
        for candidate in SUBNET.hosts():
            if candidate == GATEWAY or candidate in used:
                continue
            allocations[container_id] = str(candidate)
            write_network_state(state)
            return candidate

    raise RuntimeError(f"No available addresses in {SUBNET}")


def release_ip(container_id: str) -> None:
    with network_lock():
        state = read_network_state()
        allocations = state.setdefault("allocations", {})
        if container_id in allocations:
            del allocations[container_id]
            write_network_state(state)


def default_interface() -> str:
    route = output(["ip", "route", "get", "1.1.1.1"])
    parts = route.split()
    if "dev" not in parts:
        raise RuntimeError("Could not detect default network interface")
    return parts[parts.index("dev") + 1]


def publish_port(mapping: PortMapping, container_ip: str) -> None:
    remove_published_port_rules(mapping)
    ensure_iptables(
        [
            "iptables",
            "-t",
            "nat",
            "-A",
            "OUTPUT",
            "-p",
            mapping.protocol,
            "-o",
            "lo",
            "--dport",
            str(mapping.host),
            "-j",
            "DNAT",
            "--to-destination",
            f"{container_ip}:{mapping.container}",
        ]
    )
    ensure_iptables(
        [
            "iptables",
            "-t",
            "nat",
            "-A",
            "POSTROUTING",
            "-p",
            mapping.protocol,
            "-d",
            container_ip,
            "--dport",
            str(mapping.container),
            "-j",
            "SNAT",
            "--to-source",
            str(GATEWAY),
        ]
    )
    ensure_iptables(
        [
            "iptables",
            "-A",
            "FORWARD",
            "-p",
            mapping.protocol,
            "-d",
            container_ip,
            "--dport",
            str(mapping.container),
            "-j",
            "ACCEPT",
        ]
    )


def remove_published_port_rules(mapping: PortMapping) -> None:
    for line in iptables_save("nat"):
        if (
            line.startswith("-A OUTPUT ")
            and "--dport" in line
            and str(mapping.host) in line
            and "-j DNAT" in line
        ):
            delete_saved_rule("nat", line)
        elif (
            line.startswith("-A POSTROUTING ")
            and "--dport" in line
            and str(mapping.container) in line
            and "-j SNAT" in line
            and "10.88.0." in line
        ):
            delete_saved_rule("nat", line)

    for line in iptables_save("filter"):
        if (
            line.startswith("-A FORWARD ")
            and "--dport" in line
            and str(mapping.container) in line
            and "-j ACCEPT" in line
            and "10.88.0." in line
        ):
            delete_saved_rule("filter", line)


def iptables_save(table: str) -> list[str]:
    result = subprocess.run(["iptables-save", "-t", table], check=False, capture_output=True, text=True)
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line.startswith("-A ")]


def delete_saved_rule(table: str, saved_rule: str) -> None:
    parts = shlex.split(saved_rule)
    if len(parts) < 2 or parts[0] != "-A":
        return
    command = ["iptables"]
    if table != "filter":
        command.extend(["-t", table])
    command.extend(["-D", parts[1], *parts[2:]])
    _run_ok(command)


def write_name_resolution(rootfs: Path, name: str, container_ip: str) -> None:
    (rootfs / "etc").mkdir(parents=True, exist_ok=True)
    (rootfs / "etc/resolv.conf").write_text("nameserver 1.1.1.1\nnameserver 8.8.8.8\n")
    (rootfs / "etc/hosts").write_text(f"127.0.0.1 localhost\n{GATEWAY} host\n{container_ip} {name}\n")


def ensure_iptables(add_command: list[str]) -> None:
    check_command = add_command.copy()
    check_command[check_command.index("-A")] = "-C"
    if _run_ok(check_command) != 0:
        run(add_command)


def cleanup_network(network: dict) -> None:
    for port in network.get("ports", []):
        remove_published_port_rules(PortMapping(**port))

    host_veth = network.get("host_veth")
    if host_veth:
        _run_ok(["ip", "link", "delete", host_veth])

    container_id = network.get("container_id")
    if container_id:
        release_ip(str(container_id))


def to_jsonable(network: NetworkState) -> dict:
    value = asdict(network)
    value["ports"] = [asdict(port) for port in network.ports]
    return value


def _run_ok(command: list[str]) -> int:
    return subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False).returncode


@contextmanager
def network_lock() -> Iterator[None]:
    NETWORK_LOCK.parent.mkdir(parents=True, exist_ok=True)
    with NETWORK_LOCK.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def read_network_state() -> dict:
    NETWORK_STATE.parent.mkdir(parents=True, exist_ok=True)
    if not NETWORK_STATE.exists():
        return {"allocations": {}}
    return json.loads(NETWORK_STATE.read_text())


def write_network_state(state: dict) -> None:
    temp_path = NETWORK_STATE.with_name(f".{NETWORK_STATE.name}.{os.getpid()}.tmp")
    temp_path.write_text(json.dumps(state, indent=2) + "\n")
    os.replace(temp_path, NETWORK_STATE)


def failpoint(name: str) -> None:
    if os.environ.get("AXIS_FAILPOINT") == name:
        raise RuntimeError(f"failpoint triggered: {name}")
