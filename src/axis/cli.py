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
    copy_axisfile,
    create_container_state,
    inspect_container,
    init_state_dirs,
    list_containers,
    read_pid,
    read_json,
    read_status,
    resolve_container,
    remove_container,
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

    inspect_parser = subcommands.add_parser("inspect", help="Inspect a known container by id or name")
    inspect_parser.add_argument("container")

    logs_parser = subcommands.add_parser("logs", help="Print captured container logs")
    logs_parser.add_argument("container")
    logs_parser.add_argument("-f", "--follow", action="store_true", help="Follow logs")

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
        if args.command_name == "inspect":
            return inspect_command(args.container)
        if args.command_name == "logs":
            return logs_command(args.container, follow=args.follow)
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

    print(f"Preparing rootfs from {config.image}")
    prepare_rootfs(config, state.rootfs)
    write_runtime_config(config, state)
    state.log_file.write_text("")
    write_status(state, "created", manual_stop=False)

    try:
        return run_container_loop(config, state)
    except KeyboardInterrupt:
        print("\nInterrupted, cleaning up container")
        write_status(state, "stopped", manual_stop=True)
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


def stop_command(container_id: str) -> int:
    state = resolve_container(container_id)
    pid = read_pid(state)
    if pid is None:
        raise AxisError(f"No PID recorded for container: {container_id}")

    write_status(state, "stopping", manual_stop=True)
    terminate_pid(pid)
    write_status(state, "stopped", manual_stop=True)
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


def clean_command(container_id: str) -> int:
    state = resolve_container(container_id)
    cleanup_container_state(state.container_id)
    print(f"Removed {state.container_id}")
    return 0


def run_container_loop(config, state) -> int:
    while True:
        exit_code = run_container_once(config, state)
        status = read_status(state)
        if config.restart == "always" and not status.get("manual_stop", False):
            print(f"Restarting {state.container_id}")
            time.sleep(1)
            continue
        return exit_code


def run_container_once(config, state) -> int:
    runtime = None
    network_written = False
    try:
        runtime = start_runtime(state.runtime_config, state.log_file)
        write_pid(state, runtime.pid)
        write_status(state, "running", pid=runtime.pid, manual_stop=False)

        network = setup_network(state.container_id, runtime.pid, config, state.rootfs)
        network_json = to_jsonable(network)
        network_json["proxy_pids"] = start_port_proxies(network_json)
        write_json(state.network_file, network_json)
        network_written = True

        for mapping in config.ports:
            print(f"Published http://localhost:{mapping.host} -> {config.name}:{mapping.container}")

        exit_code = runtime.stream_until_exit()
        status = read_status(state)
        write_status(state, "exited", exit_code=exit_code, manual_stop=status.get("manual_stop", False))
        return exit_code
    except Exception:
        if runtime is not None:
            terminate_pid(runtime.pid)
        raise
    finally:
        if network_written and state.network_file.exists():
            cleanup_network_state(state)


def cleanup_container_state(container_id: str) -> None:
    container_dir = Path(".axis/containers") / container_id
    network_path = container_dir / "network.json"
    if network_path.exists():
        cleanup_network_state(resolve_container(container_id))

    pid_path = container_dir / "pid"
    if pid_path.exists():
        terminate_pid(int(pid_path.read_text().strip()))

    remove_container(container_id)


def cleanup_network_state(state) -> None:
    network = read_json(state.network_file)
    for proxy_pid in network.get("proxy_pids", []):
        terminate_pid(int(proxy_pid))
    cleanup_network(network)


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
