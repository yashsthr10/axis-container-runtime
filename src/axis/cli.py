from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from .axisfile import parse_axisfile
from .errors import AxisError
from .image import prepare_rootfs
from .network import cleanup_network, setup_network, to_jsonable
from .runtime import start_runtime, write_runtime_config
from .state import (
    add_resource,
    copy_axisfile,
    create_container_state,
    inspect_container,
    init_state_dirs,
    list_containers,
    read_pid,
    read_json,
    read_resources,
    read_status,
    resolve_container,
    remove_container,
    transition_state,
    write_json,
    write_pid,
    write_status,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="axis")
    subcommands = parser.add_subparsers(dest="command_name", required=True)

    run_parser = subcommands.add_parser("run", help="Run a container from an Axisfile")
    run_parser.add_argument("-f", "--file", type=Path, default=Path("Axisfile"))
    run_parser.add_argument("command", nargs=argparse.REMAINDER, help="Optional command override after --")

    subcommands.add_parser("ps", help="List known containers")

    stop_parser = subcommands.add_parser("stop", help="Stop a known container by id")
    stop_parser.add_argument("container_id")
    stop_parser.add_argument("--timeout", type=float, default=30.0, help="Seconds to wait before SIGKILL")

    inspect_parser = subcommands.add_parser("inspect", help="Inspect a known container by id or name")
    inspect_parser.add_argument("container")

    logs_parser = subcommands.add_parser("logs", help="Print captured container logs")
    logs_parser.add_argument("container")
    logs_parser.add_argument("-f", "--follow", action="store_true", help="Follow logs")

    stats_parser = subcommands.add_parser("stats", help="Print cgroup resource stats")
    stats_parser.add_argument("container")

    subcommands.add_parser("reconcile", help="Reconcile persisted state with live resources")

    clean_parser = subcommands.add_parser("clean", help="Remove a known container state directory")
    clean_parser.add_argument("container_id")

    args = parser.parse_args(argv)

    try:
        if args.command_name == "run":
            return run_command(args)
        if args.command_name == "ps":
            return ps_command()
        if args.command_name == "stop":
            return stop_command(args.container_id, timeout=args.timeout)
        if args.command_name == "inspect":
            return inspect_command(args.container)
        if args.command_name == "logs":
            return logs_command(args.container, follow=args.follow)
        if args.command_name == "stats":
            return stats_command(args.container)
        if args.command_name == "reconcile":
            return reconcile_command()
        if args.command_name == "clean":
            return clean_command(args.container_id)
    except AxisError as exc:
        print(f"axis: {exc}", file=sys.stderr)
        return 1

    return 0


def run_command(args: argparse.Namespace) -> int:
    require_root()
    init_state_dirs()

    command_override = args.command if args.command else None
    if command_override and command_override[0] == "--":
        command_override = command_override[1:]

    config = parse_axisfile(args.file, command_override=command_override)
    state = create_container_state(config.name)
    copy_axisfile(args.file, state)
    transition_state(state, "created", desired_state="running", manual_stop=False)
    add_resource(state, {"type": "rootfs", "path": str(state.rootfs)})

    print(f"Preparing rootfs from {config.image}")
    prepare_rootfs(config, state.rootfs)
    failpoint("after-rootfs-create")
    write_runtime_config(config, state)
    runtime_config = read_json(state.runtime_config)
    add_resource(state, {"type": "cgroup", "path": runtime_config["cgroup_path"]})
    for destination, source in runtime_config.get("bind_mounts", {}).items():
        add_resource(state, {"type": "bind_mount", "source": source, "destination": destination})
    state.log_file.write_text("")

    try:
        return run_container_loop(config, state)
    except KeyboardInterrupt:
        print("\nInterrupted, cleaning up container")
        write_status(state, "stopping", manual_stop=True, desired_state="exited")
        cleanup_container_state(state.directory.name)
        return 130


def ps_command() -> int:
    rows = list_containers()
    if not rows:
        print("No containers")
        return 0

    print("ID\tNAME\tPID\tROOTFS")
    for row in rows:
        print(f"{row['id']}\t{row['name']}\t{row['pid']}\t{row['rootfs']}")
    return 0


def stop_command(container_id: str, timeout: float = 30.0) -> int:
    state = resolve_container(container_id)
    status = read_status(state)
    if status["state"] in {"exited", "failed", "deleted"} or not pid_alive_or_unknown(state):
        write_status(state, "exited", manual_stop=True, desired_state="exited")
        print(f"Stopped {state.container_id}")
        return 0

    transition_state(state, "stopping", manual_stop=True, desired_state="exited")
    stop_container_processes(state, timeout=timeout)
    transition_state(state, "exited", manual_stop=True, desired_state="exited", exit_reason="stopped")
    print(f"Stopped {state.container_id}")
    return 0


def inspect_command(container: str) -> int:
    print(json.dumps(inspect_container(container), indent=2))
    return 0


def logs_command(container: str, follow: bool = False) -> int:
    state = resolve_container(container)
    if not state.log_file.exists():
        raise AxisError(f"No logs found for container: {container}")

    with state.log_file.open() as logs:
        for line in logs:
            print(line, end="")

        while follow:
            line = logs.readline()
            if line:
                print(line, end="")
                continue
            time.sleep(0.5)

    return 0


def stats_command(container: str) -> int:
    state = resolve_container(container)
    runtime = read_json(state.runtime_config)
    print(json.dumps(read_cgroup_stats(Path(runtime["cgroup_path"])), indent=2))
    return 0


def reconcile_command() -> int:
    containers_dir = Path(".axis/containers")
    if not containers_dir.exists():
        print("No containers")
        return 0

    repaired = []
    for container_dir in sorted(containers_dir.iterdir()):
        if not (container_dir / "runtime.json").exists():
            continue
        state = resolve_container(container_dir.name)
        status = read_status(state)
        pid = read_pid(state)
        if status["state"] in {"running", "starting", "stopping"} and not is_pid_alive(pid):
            try:
                write_status(state, "failed", pid=None, exit_reason="stale_pid", desired_state="exited")
                repaired.append(f"{state.container_id}: marked failed due to stale pid")
            except PermissionError:
                repaired.append(f"{state.container_id}: stale pid detected, rerun reconcile as root to repair")

        if state.network_file.exists():
            network = read_json(state.network_file)
            live_proxies = []
            for proxy_pid in network.get("proxy_pids", []):
                if is_pid_alive(int(proxy_pid)):
                    live_proxies.append(proxy_pid)
            if len(live_proxies) != len(network.get("proxy_pids", [])):
                try:
                    network["proxy_pids"] = live_proxies
                    write_json(state.network_file, network)
                    repaired.append(f"{state.container_id}: pruned stale proxy pids")
                except PermissionError:
                    repaired.append(f"{state.container_id}: stale proxy pids detected, rerun reconcile as root to repair")

    for line in repaired:
        print(line)
    if not repaired:
        print("State is already reconciled")
    return 0


def clean_command(container_id: str) -> int:
    try:
        state = resolve_container(container_id)
    except AxisError:
        if not (Path(".axis/containers") / container_id).exists():
            print(f"Removed {container_id}")
            return 0
        raise
    cleanup_container_state(state.container_id)
    print(f"Removed {state.container_id}")
    return 0


def run_container_loop(config, state) -> int:
    while True:
        status = read_status(state)
        transition_state(
            state,
            "starting",
            desired_state="running",
            manual_stop=status.get("manual_stop", False),
            restart_count=status.get("restart_count", 0),
        )
        exit_code = run_container_once(config, state)
        status = read_status(state)
        if config.restart == "always" and not status.get("manual_stop", False):
            print(f"Restarting {state.container_id}")
            write_status(state, "exited", restart_count=status.get("restart_count", 0) + 1)
            time.sleep(1)
            continue
        return exit_code


def run_container_once(config, state) -> int:
    runtime = None
    network_written = False
    try:
        failpoint("before-runtime-start")
        runtime = start_runtime(state.runtime_config, state.log_file)
        write_pid(state, runtime.pid)
        transition_state(state, "running", pid=runtime.pid, manual_stop=False, desired_state="running")
        failpoint("after-runtime-start")

        network = setup_network(state.container_id, runtime.pid, config, state.rootfs)
        network_json = to_jsonable(network)
        add_resource(
            state,
            {
                "type": "veth",
                "host": network_json["host_veth"],
                "container": network_json["container_veth"],
            },
        )
        add_resource(state, {"type": "ip", "network": network_json["bridge"], "address": network_json["container_ip"]})
        failpoint("after-network-setup")
        network_json["proxy_pids"] = start_port_proxies(state, network_json)
        write_json(state.network_file, network_json)
        network_written = True
        failpoint("after-proxy-start")

        for mapping in config.ports:
            print(f"Published http://localhost:{mapping.host} -> {config.name}:{mapping.container}")

        exit_code = runtime.stream_until_exit()
        status = read_status(state)
        runtime_config = read_json(state.runtime_config)
        stats = read_cgroup_stats(Path(runtime_config["cgroup_path"]))
        exit_details = exit_details_from_code(exit_code, stats)
        transition_state(
            state,
            "exited",
            exit_code=exit_code,
            pid=None,
            manual_stop=status.get("manual_stop", False),
            **exit_details,
        )
        return exit_code
    except Exception:
        if runtime is not None:
            terminate_pid(runtime.pid, force=True)
        write_status(state, "failed", exit_reason="runtime_error", desired_state="exited")
        raise
    finally:
        if network_written and state.network_file.exists():
            cleanup_network_state(state)


def cleanup_container_state(container_id: str) -> None:
    container_dir = Path(".axis/containers") / container_id
    if not container_dir.exists():
        return
    state = resolve_container(container_id)
    write_status(state, "stopping", manual_stop=True, desired_state="deleted")
    network_path = container_dir / "network.json"
    if network_path.exists():
        cleanup_network_state(state)

    stop_container_processes(state, timeout=5.0)
    cleanup_owned_resources(state)
    write_status(state, "deleted", manual_stop=True, desired_state="deleted")

    remove_container(container_id)


def cleanup_network_state(state) -> None:
    network = read_json(state.network_file)
    for proxy_pid in network.get("proxy_pids", []):
        terminate_pid(int(proxy_pid), force=True)
    cleanup_network(network)


def terminate_pid(pid: int, force: bool = False) -> None:
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return

    if force:
        wait_until_dead(pid, timeout=1.0)
        if is_pid_alive(pid):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                return

    wait_until_dead(pid, timeout=1.0)


def start_port_proxies(state, network: dict) -> list[int]:
    proxy_pids = []
    container_ip = network["container_ip"]
    for port in network.get("ports", []):
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "axis.proxy",
                "--listen-host",
                "127.0.0.1",
                "--listen-port",
                str(port["host"]),
                "--target-host",
                container_ip,
                "--target-port",
                str(port["container"]),
            ],
            start_new_session=True,
        )
        time.sleep(0.05)
        if process.poll() is not None:
            raise AxisError(f"Port proxy failed to start for localhost:{port['host']}")
        proxy_pids.append(process.pid)
        add_resource(state, {"type": "proxy", "pid": process.pid, "host_port": port["host"]})
    return proxy_pids


def is_pid_alive(pid: int | None) -> bool:
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def pid_alive_or_unknown(state) -> bool:
    return is_pid_alive(read_pid(state))


def wait_until_dead(pid: int, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not is_pid_alive(pid):
            return True
        time.sleep(0.05)
    return not is_pid_alive(pid)


def stop_container_processes(state, timeout: float) -> None:
    runtime = read_json(state.runtime_config) if state.runtime_config.exists() else {}
    cgroup_path = Path(runtime.get("cgroup_path", ""))
    procs = read_cgroup_procs(cgroup_path)
    if procs:
        for pid in procs:
            terminate_pid(pid)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and read_cgroup_procs(cgroup_path):
            time.sleep(0.1)
        remaining = read_cgroup_procs(cgroup_path)
        if remaining:
            cgroup_kill = cgroup_path / "cgroup.kill"
            if cgroup_kill.exists():
                cgroup_kill.write_text("1\n")
            else:
                for pid in remaining:
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
        return

    pid = read_pid(state)
    if pid is not None:
        terminate_pid(pid, force=True)


def read_cgroup_procs(cgroup_path: Path) -> list[int]:
    procs_path = cgroup_path / "cgroup.procs"
    if not procs_path.exists():
        return []
    procs = []
    for line in procs_path.read_text().splitlines():
        try:
            procs.append(int(line))
        except ValueError:
            continue
    return procs


def read_cgroup_stats(cgroup_path: Path) -> dict:
    stats: dict[str, object] = {"cgroup_path": str(cgroup_path), "available": cgroup_path.exists()}
    for name in ("memory.current", "memory.peak", "memory.max", "pids.current", "pids.max"):
        path = cgroup_path / name
        if path.exists():
            stats[name.replace(".", "_")] = path.read_text().strip()
    for name in ("memory.events", "cpu.stat", "cgroup.events", "io.stat"):
        path = cgroup_path / name
        if path.exists():
            stats[name.replace(".", "_")] = parse_key_value_file(path)
    return stats


def parse_key_value_file(path: Path) -> dict[str, int | str]:
    values: dict[str, int | str] = {}
    for line in path.read_text().splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        try:
            values[parts[0]] = int(parts[1])
        except ValueError:
            values[parts[0]] = parts[1]
    return values


def exit_details_from_code(exit_code: int, stats: dict) -> dict:
    memory_events = stats.get("memory_events", {})
    oom_killed = isinstance(memory_events, dict) and int(memory_events.get("oom_kill", 0)) > 0
    if oom_killed:
        return {"exit_reason": "oom_killed", "oom_killed": True}
    if exit_code >= 128:
        return {"exit_signal": exit_code - 128, "exit_reason": "signal"}
    if exit_code == 0:
        return {"exit_reason": "completed", "oom_killed": False}
    return {"exit_reason": "error", "oom_killed": False}


def cleanup_owned_resources(state) -> None:
    runtime = read_json(state.runtime_config) if state.runtime_config.exists() else {}
    cgroup_path = Path(runtime.get("cgroup_path", ""))
    if cgroup_path.exists():
        try:
            cgroup_path.rmdir()
        except OSError:
            pass


def failpoint(name: str) -> None:
    if os.environ.get("AXIS_FAILPOINT") == name:
        raise AxisError(f"failpoint triggered: {name}")


def require_root() -> None:
    if os.geteuid() != 0:
        raise AxisError("axis run currently requires root. Use sudo axis run.")


if __name__ == "__main__":
    raise SystemExit(main())
