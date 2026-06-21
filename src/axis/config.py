from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .ports import PortMapping


@dataclass(frozen=True)
class CopySpec:
    source: Path
    destination: str


@dataclass(frozen=True)
class VolumeSpec:
    source: Path
    destination: str


@dataclass(frozen=True)
class ResourceLimits:
    memory: str | None = None
    cpu: str | None = None


@dataclass(frozen=True)
class AxisConfig:
    image: str
    command: list[str]
    name: str = "axis-container"
    hostname: str | None = None
    workdir: str = "/"
    env: dict[str, str] = field(default_factory=dict)
    copies: list[CopySpec] = field(default_factory=list)
    volumes: list[VolumeSpec] = field(default_factory=list)
    exposed_ports: list[int] = field(default_factory=list)
    ports: list[PortMapping] = field(default_factory=list)
    resources: ResourceLimits = field(default_factory=ResourceLimits)
    restart: str | None = None

    @property
    def resolved_hostname(self) -> str:
        return self.hostname or self.name
