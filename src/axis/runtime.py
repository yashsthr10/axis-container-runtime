from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from .config import AxisConfig
from .errors import AxisError
from .state import ContainerState


RUNTIME_BINARY = Path(
    os.environ.get(
        "AXIS_RUNTIME_BINARY",
        Path(__file__).resolve().parents[1] / "runtime" / "axis-runtime",
    )
)


class RuntimeProcess:
    def __init__(self, process: subprocess.Popen[str], pid: int, log_path: Path) -> None:
        self.process = process
        self.pid = pid
        self.log_path = log_path

    def stream_until_exit(self) -> int:
        if self.process.stdout is not None:
            for line in self.process.stdout:
                _tee_line(line, self.log_path)
        return self.process.wait()


def write_runtime_config(config: AxisConfig, state: ContainerState) -> None:
    for volume in config.volumes:
        if not volume.source.is_dir():
            raise AxisError(f"Volume source must be an existing directory: {volume.source}")

    runtime_config = {
        "name": config.name,
        "rootfs": str(state.rootfs.resolve()),
        "hostname": config.resolved_hostname,
        "workdir": config.workdir,
        "command": config.command,
        "env": config.env,
        "ports": [f"{mapping.host}:{mapping.container}" for mapping in config.ports],
        "bind_mounts": {volume.destination: str(volume.source) for volume in config.volumes},
        "restart": config.restart,
        "cgroup_path": f"/sys/fs/cgroup/axis/{state.container_id}",
        "memory": config.resources.memory,
        "cpu": config.resources.cpu,
    }
    state.runtime_config.write_text(json.dumps(runtime_config, indent=2) + "\n")


def start_runtime(config_path: Path, log_path: Path) -> RuntimeProcess:
    if not RUNTIME_BINARY.exists():
        raise AxisError(f"Runtime binary not found: {RUNTIME_BINARY}. Run `make build` first.")

    process = subprocess.Popen(
        [str(RUNTIME_BINARY), str(config_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    assert process.stdout is not None
    for line in process.stdout:
        _tee_line(line, log_path)
        if line.startswith("AXIS_PID "):
            return RuntimeProcess(process, int(line.split()[1]), log_path)
        if process.poll() is not None:
            break

    raise AxisError("Runtime exited before reporting a container PID")


def _tee_line(line: str, log_path: Path) -> None:
    print(line, end="")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a") as log:
        log.write(line)
