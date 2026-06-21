from __future__ import annotations

import json
import os
import shutil
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from .errors import AxisError


STATE_DIR = Path(".axis")


@dataclass(frozen=True)
class ContainerState:
    container_id: str
    name: str
    directory: Path
    rootfs: Path
    runtime_config: Path
    axisfile_copy: Path
    pid_file: Path
    network_file: Path
    log_file: Path
    status_file: Path


def create_container_state(name: str) -> ContainerState:
    container_id = f"{name}-{uuid.uuid4().hex[:8]}"
    directory = STATE_DIR / "containers" / container_id
    rootfs = directory / "rootfs"
    directory.mkdir(parents=True, exist_ok=False)
    rootfs.mkdir(parents=True, exist_ok=False)

    return ContainerState(
        container_id=container_id,
        name=name,
        directory=directory,
        rootfs=rootfs,
        runtime_config=directory / "runtime.json",
        axisfile_copy=directory / "Axisfile",
        pid_file=directory / "pid",
        network_file=directory / "network.json",
        log_file=directory / "logs.txt",
        status_file=directory / "status.json",
    )


def init_state_dirs() -> None:
    for path in (STATE_DIR / "images", STATE_DIR / "containers", STATE_DIR / "networks"):
        path.mkdir(parents=True, exist_ok=True)


def copy_axisfile(source: Path, state: ContainerState) -> None:
    shutil.copy2(source, state.axisfile_copy)


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def write_pid(state: ContainerState, pid: int) -> None:
    state.pid_file.write_text(f"{pid}\n")


def container_state_from_dir(container_dir: Path) -> ContainerState:
    runtime_path = container_dir / "runtime.json"
    runtime = read_json(runtime_path) if runtime_path.exists() else {}
    return ContainerState(
        container_id=container_dir.name,
        name=runtime.get("name", container_dir.name),
        directory=container_dir,
        rootfs=container_dir / "rootfs",
        runtime_config=runtime_path,
        axisfile_copy=container_dir / "Axisfile",
        pid_file=container_dir / "pid",
        network_file=container_dir / "network.json",
        log_file=container_dir / "logs.txt",
        status_file=container_dir / "status.json",
    )


def resolve_container(reference: str) -> ContainerState:
    containers_dir = STATE_DIR / "containers"
    if not containers_dir.exists():
        raise AxisError(f"Unknown container: {reference}")

    exact = containers_dir / reference
    if exact.is_dir() and (exact / "runtime.json").exists():
        return container_state_from_dir(exact)

    matches = []
    for container_dir in sorted(containers_dir.iterdir()):
        runtime_path = container_dir / "runtime.json"
        if not runtime_path.exists():
            continue
        runtime = read_json(runtime_path)
        if runtime.get("name") == reference:
            matches.append(container_state_from_dir(container_dir))

    if not matches:
        raise AxisError(f"Unknown container: {reference}")
    if len(matches) > 1:
        ids = ", ".join(match.container_id for match in matches)
        raise AxisError(f"Container name {reference} is ambiguous: {ids}")
    return matches[0]


def read_pid(state: ContainerState) -> int | None:
    if not state.pid_file.exists():
        return None
    try:
        return int(state.pid_file.read_text().strip())
    except ValueError:
        return None


def pid_alive(pid: int | None) -> bool:
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def write_status(state: ContainerState, status: str, **extra: object) -> None:
    payload = {"status": status, **extra}
    write_json(state.status_file, payload)


def read_status(state: ContainerState) -> dict:
    if not state.status_file.exists():
        return {}
    return read_json(state.status_file)


def inspect_container(reference: str) -> dict:
    state = resolve_container(reference)
    runtime = read_json(state.runtime_config)
    status = read_status(state)
    pid = read_pid(state)
    running = pid_alive(pid)
    network = read_json(state.network_file) if state.network_file.exists() else {}
    ports = [
        f"{mapping.get('host')}:{mapping.get('container')}"
        for mapping in network.get("ports", [])
        if mapping.get("host") is not None and mapping.get("container") is not None
    ]
    if not ports:
        ports = runtime.get("ports", [])

    return {
        "id": state.container_id,
        "pid": pid if running else None,
        "ip": network.get("container_ip"),
        "ports": ports,
        "memory": runtime.get("memory"),
        "status": "running" if running else status.get("status", "unknown"),
    }


def list_containers() -> list[dict]:
    containers_dir = STATE_DIR / "containers"
    if not containers_dir.exists():
        return []

    rows = []
    for container_dir in sorted(containers_dir.iterdir()):
        runtime_path = container_dir / "runtime.json"
        if not runtime_path.exists():
            continue
        state = container_state_from_dir(container_dir)
        runtime = read_json(runtime_path)
        pid = read_pid(state)
        rows.append(
            {
                "id": container_dir.name,
                "name": runtime.get("name", container_dir.name),
                "pid": str(pid) if pid_alive(pid) else "",
                "rootfs": runtime.get("rootfs", ""),
            }
        )
    return rows


def remove_container(container_id: str) -> None:
    shutil.rmtree(STATE_DIR / "containers" / container_id, ignore_errors=True)


def dataclass_dict(value: object) -> dict:
    return asdict(value)
