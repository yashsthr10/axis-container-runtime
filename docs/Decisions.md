# Decisions

This file records decisions that explain why Axis is shaped the way it is.

## Decision Index

- `DEC-001`: Python CLI plus C++ runtime executable.
- `DEC-002`: File-backed state under `.axis`.
- `DEC-003`: Docker CLI for image rootfs preparation.
- `DEC-004`: Python TCP proxies for published ports.
- `DEC-005`: Foreground-only restart policy.
- `DEC-006`: Directory-only bind volumes.

## DEC-001: Python CLI Plus C++ Runtime Executable

- **Status**: accepted
- **Context**: Axis needs readable orchestration code and direct Linux syscalls.
- **Decision**: Use Python for CLI/orchestration and a separate C++ executable for namespace/cgroup/mount/process setup.
- **Alternatives considered**: Cython, `ctypes`, one all-C++ binary, one all-Python implementation.
- **Why this choice**: A subprocess boundary is simple, debuggable, and avoids native Python extension complexity.
- **Consequences**:
  - Python and C++ communicate through `runtime.json` and stdout.
  - Runtime JSON must stay synchronized across both sides.
  - C++ can be built and tested independently.

## DEC-002: File-Backed State Under `.axis`

- **Status**: accepted
- **Context**: Commands such as `ps`, `stop`, `inspect`, and `logs` need state after `axis run` starts.
- **Decision**: Persist state in `.axis/containers/<id>/` and `.axis/networks/`.
- **Alternatives considered**: SQLite, long-running daemon, in-memory state only.
- **Why this choice**: Files are transparent and easy to inspect for an educational runtime.
- **Consequences**:
  - State may become stale.
  - Commands need live PID checks.
  - Cleanup must be idempotent.

## DEC-003: Docker CLI For Rootfs Preparation

- **Status**: accepted
- **Context**: Axis needs a root filesystem from an image but is not an image registry client.
- **Decision**: Use Docker CLI commands to pull/create/export/remove image containers.
- **Alternatives considered**: OCI registry implementation, direct containerd integration, prebuilt rootfs only.
- **Why this choice**: Keeps focus on runtime mechanics.
- **Consequences**:
  - Docker must be installed and working.
  - Image extraction behavior follows Docker.

## DEC-004: Python TCP Proxies For Published Ports

- **Status**: accepted
- **Context**: Localhost port publishing is required for examples.
- **Decision**: Start Python proxy processes from `axis.proxy` for `PORT` mappings.
- **Alternatives considered**: iptables DNAT only, C++ proxying, no port publishing.
- **Why this choice**: Easy to reason about and works with localhost flows.
- **Consequences**:
  - Each port mapping has a proxy PID stored in `network.json`.
  - Proxy cleanup is required.
  - Existing `publish_port()` iptables helper is not used by the main run flow.

## DEC-005: Foreground-Only Restart Policy

- **Status**: accepted
- **Context**: `RESTART always` is useful, but a daemon/supervisor would significantly expand the system.
- **Decision**: Implement restart in the attached Python `axis run` loop.
- **Alternatives considered**: daemon process, systemd integration, C++ parent supervision.
- **Why this choice**: Minimal behavior that teaches restart supervision without adding daemon architecture.
- **Consequences**:
  - Restarts stop when `axis run` exits.
  - `axis stop` writes `manual_stop=true` to prevent relaunch.

## DEC-006: Directory-Only Bind Volumes

- **Status**: accepted
- **Context**: `VOLUME ./data:/data` teaches bind mounts.
- **Decision**: Support host directory bind mounts only.
- **Alternatives considered**: file mounts, anonymous volumes, managed volume store.
- **Why this choice**: Directory mounts cover the learning goal and avoid file target edge cases.
- **Consequences**:
  - Python requires source to be an existing directory.
  - C++ creates destination directories before `mount`.
  - File bind mounts can be added later with target-type handling.
