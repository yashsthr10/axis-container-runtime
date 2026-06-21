from __future__ import annotations

from dataclasses import dataclass

from .errors import AxisfileError


@dataclass(frozen=True)
class PortMapping:
    host: int
    container: int
    protocol: str = "tcp"


def parse_port_mapping(value: str) -> PortMapping:
    raw = value.strip()
    protocol = "tcp"
    if "/" in raw:
        raw, protocol = raw.rsplit("/", 1)
        protocol = protocol.lower()

    if protocol != "tcp":
        raise AxisfileError(f"Only tcp port mappings are supported for now: {value}")

    parts = raw.split(":")
    if len(parts) == 1:
        host_port = container_port = _parse_port(parts[0], value)
    elif len(parts) == 2:
        host_port = _parse_port(parts[0], value)
        container_port = _parse_port(parts[1], value)
    else:
        raise AxisfileError(f"Invalid port mapping: {value}")

    return PortMapping(host=host_port, container=container_port, protocol=protocol)


def _parse_port(value: str, original: str) -> int:
    try:
        port = int(value)
    except ValueError as exc:
        raise AxisfileError(f"Invalid port in mapping {original}: {value}") from exc

    if port < 1 or port > 65535:
        raise AxisfileError(f"Port out of range in mapping {original}: {port}")

    return port
