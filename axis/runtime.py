from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from .config import AxisConfig
from .errors import AxisError
from .state import ContainerState


RUNTIME_BINARY = Path("runtime/axis-runtime")


class RuntimeProcess:
    def __init__(self, process: subprocess.Popen[str], pid: int) -> None:
        self.process = process
        self.pid = pid

    def stream_until_exit(self) -> int:
        if self.process.stdout is not None:
            for line in self.process.stdout:
                print(line, end="")
        return self.process.wait()


def write_runtime_config(config: AxisConfig, state: ContainerState) -> None:
    runtime_config = {
        "name": config.name,
        "rootfs": str(state.rootfs.resolve()),
        "hostname": config.resolved_hostname,
        "workdir": config.workdir,
        "command": config.command,
        "env": config.env,
        "cgroup_path": f"/sys/fs/cgroup/axis/{state.container_id}",
        "memory": config.resources.memory,
        "cpu": config.resources.cpu,
    }
    state.runtime_config.write_text(json.dumps(runtime_config, indent=2) + "\n")


def start_runtime(config_path: Path) -> RuntimeProcess:
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
        print(line, end="")
        if line.startswith("AXIS_PID "):
            return RuntimeProcess(process, int(line.split()[1]))
        if process.poll() is not None:
            break

    raise AxisError("Runtime exited before reporting a container PID")
