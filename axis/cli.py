from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
from pathlib import Path

from .axisfile import parse_axisfile
from .errors import AxisError
from .image import prepare_rootfs
from .network import cleanup_network, setup_network, to_jsonable
from .runtime import start_runtime, write_runtime_config
from .state import (
    copy_axisfile,
    create_container_state,
    init_state_dirs,
    list_containers,
    read_json,
    remove_container,
    write_json,
    write_pid,
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

    clean_parser = subcommands.add_parser("clean", help="Remove a known container state directory")
    clean_parser.add_argument("container_id")

    args = parser.parse_args(argv)

    try:
        if args.command_name == "run":
            return run_command(args)
        if args.command_name == "ps":
            return ps_command()
        if args.command_name == "stop":
            return stop_command(args.container_id)
        if args.command_name == "clean":
            return clean_command(args.container_id)
    except AxisError as exc:
        print(f"axis: {exc}", file=sys.stderr)
        return 1

    return 0


def run_command(args: argparse.Namespace) -> int:
    require_root()
    init_state_dirs()
    runtime = None
    network_written = False

    command_override = args.command if args.command else None
    if command_override and command_override[0] == "--":
        command_override = command_override[1:]

    config = parse_axisfile(args.file, command_override=command_override)
    state = create_container_state(config.name)
    copy_axisfile(args.file, state)

    print(f"Preparing rootfs from {config.image}")
    prepare_rootfs(config, state.rootfs)
    write_runtime_config(config, state)

    try:
        runtime = start_runtime(state.runtime_config)
        write_pid(state, runtime.pid)

        network = setup_network(state.container_id, runtime.pid, config, state.rootfs)
        network_json = to_jsonable(network)
        network_json["proxy_pids"] = start_port_proxies(network_json)
        write_json(state.network_file, network_json)
        network_written = True

        for mapping in config.ports:
            print(f"Published http://localhost:{mapping.host} -> {config.name}:{mapping.container}")

        return runtime.stream_until_exit()
    except KeyboardInterrupt:
        print("\nInterrupted, cleaning up container")
        cleanup_container_state(state.directory.name)
        return 130
    except Exception:
        if runtime is not None:
            terminate_pid(runtime.pid)
        if network_written and state.network_file.exists():
            cleanup_network(read_json(state.network_file))
        raise


def ps_command() -> int:
    rows = list_containers()
    if not rows:
        print("No containers")
        return 0

    print("ID\tNAME\tPID\tROOTFS")
    for row in rows:
        print(f"{row['id']}\t{row['name']}\t{row['pid']}\t{row['rootfs']}")
    return 0


def stop_command(container_id: str) -> int:
    pid_path = Path(".axis/containers") / container_id / "pid"
    if not pid_path.exists():
        raise AxisError(f"Unknown container: {container_id}")

    pid = int(pid_path.read_text().strip())
    terminate_pid(pid)
    print(f"Stopped {container_id}")
    return 0


def clean_command(container_id: str) -> int:
    cleanup_container_state(container_id)
    print(f"Removed {container_id}")
    return 0


def cleanup_container_state(container_id: str) -> None:
    container_dir = Path(".axis/containers") / container_id
    network_path = container_dir / "network.json"
    if network_path.exists():
        network = read_json(network_path)
        for proxy_pid in network.get("proxy_pids", []):
            terminate_pid(int(proxy_pid))
        cleanup_network(network)

    pid_path = container_dir / "pid"
    if pid_path.exists():
        terminate_pid(int(pid_path.read_text().strip()))

    remove_container(container_id)


def terminate_pid(pid: int) -> None:
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return

    try:
        os.waitpid(pid, 0)
    except ChildProcessError:
        pass


def start_port_proxies(network: dict) -> list[int]:
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
        proxy_pids.append(process.pid)
    return proxy_pids


def require_root() -> None:
    if os.geteuid() != 0:
        raise AxisError("axis run currently requires root. Use sudo axis run.")


if __name__ == "__main__":
    raise SystemExit(main())
