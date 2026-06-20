from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path


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


def list_containers() -> list[dict]:
    containers_dir = STATE_DIR / "containers"
    if not containers_dir.exists():
        return []

    rows = []
    for container_dir in sorted(containers_dir.iterdir()):
        runtime_path = container_dir / "runtime.json"
        pid_path = container_dir / "pid"
        if not runtime_path.exists():
            continue
        runtime = read_json(runtime_path)
        rows.append(
            {
                "id": container_dir.name,
                "name": runtime.get("name", container_dir.name),
                "pid": pid_path.read_text().strip() if pid_path.exists() else "",
                "rootfs": runtime.get("rootfs", ""),
            }
        )
    return rows


def remove_container(container_id: str) -> None:
    shutil.rmtree(STATE_DIR / "containers" / container_id, ignore_errors=True)


def dataclass_dict(value: object) -> dict:
    return asdict(value)
