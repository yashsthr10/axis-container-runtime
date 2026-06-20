from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .config import AxisConfig
from .errors import CommandError
from .process import output, run


def prepare_rootfs(config: AxisConfig, rootfs: Path) -> None:
    run(["docker", "pull", config.image])
    docker_container = output(["docker", "create", config.image])
    try:
        _export_container(docker_container, rootfs)
    finally:
        run(["docker", "rm", docker_container])

    for copy_spec in config.copies:
        destination = _safe_rootfs_path(rootfs, copy_spec.destination)
        if copy_spec.source.is_dir():
            shutil.copytree(copy_spec.source, destination, dirs_exist_ok=True)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(copy_spec.source, destination)


def _export_container(container_id: str, rootfs: Path) -> None:
    export_process = subprocess.Popen(["docker", "export", container_id], stdout=subprocess.PIPE)
    tar_process = subprocess.Popen(["tar", "-C", str(rootfs), "-xf", "-"], stdin=export_process.stdout)
    assert export_process.stdout is not None
    export_process.stdout.close()

    tar_exit = tar_process.wait()
    export_exit = export_process.wait()
    if export_exit != 0 or tar_exit != 0:
        raise CommandError(f"Failed to export Docker image filesystem for {container_id}")


def _safe_rootfs_path(rootfs: Path, destination: str) -> Path:
    relative = destination.lstrip("/")
    path = (rootfs / relative).resolve()
    rootfs_resolved = rootfs.resolve()
    if rootfs_resolved != path and rootfs_resolved not in path.parents:
        raise CommandError(f"COPY destination escapes rootfs: {destination}")
    return path
