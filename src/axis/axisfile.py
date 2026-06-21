from __future__ import annotations

import shlex
from pathlib import Path

from .config import AxisConfig, CopySpec, ResourceLimits, VolumeSpec
from .errors import AxisfileError
from .ports import parse_port_mapping


def parse_axisfile(path: Path, command_override: list[str] | None = None) -> AxisConfig:
    if not path.exists():
        raise AxisfileError(f"Axisfile not found: {path}")

    image: str | None = None
    name = "axis-container"
    hostname: str | None = None
    workdir = "/"
    command: list[str] | None = None
    env: dict[str, str] = {}
    copies: list[CopySpec] = []
    volumes: list[VolumeSpec] = []
    exposed_ports: list[int] = []
    ports = []
    memory: str | None = None
    cpu: str | None = None
    restart: str | None = None

    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        instruction, _, rest = stripped.partition(" ")
        instruction = instruction.upper()
        rest = rest.strip()

        if instruction == "FROM":
            image = _require_value(instruction, rest, line_number)
        elif instruction == "NAME":
            name = _require_value(instruction, rest, line_number)
        elif instruction == "HOSTNAME":
            hostname = _require_value(instruction, rest, line_number)
        elif instruction == "WORKDIR":
            workdir = _require_value(instruction, rest, line_number)
        elif instruction == "COPY":
            parts = _split(rest, line_number)
            if len(parts) != 2:
                raise AxisfileError(f"Line {line_number}: COPY requires source and destination")
            copies.append(CopySpec(source=(path.parent / parts[0]).resolve(), destination=parts[1]))
        elif instruction == "VOLUME":
            volumes.append(_parse_volume(_require_value(instruction, rest, line_number), path.parent, line_number))
        elif instruction == "ENV":
            key, value = _parse_env(rest, line_number)
            env[key] = value
        elif instruction == "EXPOSE":
            exposed_ports.append(_parse_port(rest, line_number))
        elif instruction == "PORT":
            ports.append(parse_port_mapping(_require_value(instruction, rest, line_number)))
        elif instruction == "MEMORY":
            memory = _require_value(instruction, rest, line_number)
        elif instruction == "CPU":
            cpu = _require_value(instruction, rest, line_number)
        elif instruction == "RESTART":
            restart = _parse_restart(_require_value(instruction, rest, line_number), line_number)
        elif instruction == "CMD":
            command = _split(_require_value(instruction, rest, line_number), line_number)
        else:
            raise AxisfileError(f"Line {line_number}: unsupported instruction {instruction}")

    if image is None:
        raise AxisfileError("Axisfile must include FROM")

    if command_override is not None:
        command = command_override

    if not command:
        raise AxisfileError("Axisfile must include CMD or the CLI must provide a command override")

    return AxisConfig(
        image=image,
        name=name,
        hostname=hostname,
        workdir=workdir,
        command=command,
        env=env,
        copies=copies,
        volumes=volumes,
        exposed_ports=exposed_ports,
        ports=ports,
        resources=ResourceLimits(memory=memory, cpu=cpu),
        restart=restart,
    )


def _require_value(instruction: str, value: str, line_number: int) -> str:
    if not value:
        raise AxisfileError(f"Line {line_number}: {instruction} requires a value")
    return value


def _split(value: str, line_number: int) -> list[str]:
    try:
        return shlex.split(value)
    except ValueError as exc:
        raise AxisfileError(f"Line {line_number}: {exc}") from exc


def _parse_env(value: str, line_number: int) -> tuple[str, str]:
    if "=" not in value:
        raise AxisfileError(f"Line {line_number}: ENV must use KEY=VALUE")

    key, env_value = value.split("=", 1)
    key = key.strip()
    if not key:
        raise AxisfileError(f"Line {line_number}: ENV key cannot be empty")

    return key, env_value


def _parse_volume(value: str, base_dir: Path, line_number: int) -> VolumeSpec:
    if ":" not in value:
        raise AxisfileError(f"Line {line_number}: VOLUME must use source:destination")

    source, destination = value.split(":", 1)
    source = source.strip()
    destination = destination.strip()
    if not source or not destination:
        raise AxisfileError(f"Line {line_number}: VOLUME source and destination cannot be empty")
    if not destination.startswith("/"):
        raise AxisfileError(f"Line {line_number}: VOLUME destination must be an absolute path")
    if destination == "/" or "/../" in destination or destination.endswith("/.."):
        raise AxisfileError(f"Line {line_number}: VOLUME destination must stay inside the container rootfs")

    return VolumeSpec(source=(base_dir / source).resolve(), destination=destination)


def _parse_restart(value: str, line_number: int) -> str:
    policy = value.strip().lower()
    if policy != "always":
        raise AxisfileError(f"Line {line_number}: unsupported RESTART policy {value}")
    return policy


def _parse_port(value: str, line_number: int) -> int:
    try:
        port = int(value)
    except ValueError as exc:
        raise AxisfileError(f"Line {line_number}: invalid EXPOSE port {value}") from exc

    if port < 1 or port > 65535:
        raise AxisfileError(f"Line {line_number}: EXPOSE port out of range {port}")

    return port
