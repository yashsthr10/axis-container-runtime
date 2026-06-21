# Structure

This repository is small and intentionally flat. Keep new code near the behavior it supports.

## Top-Level Layout

- `src/axis/`: Python package and CLI control plane.
- `src/runtime/`: C++ runtime binary source and runtime Makefile.
- `tests/unit/`: fast unit tests that do not require root.
- `tests/integration/`: root-gated integration tests and placeholders for namespace/network behavior.
- `examples/fastapi/`: runnable example app and `Axisfile`.
- `docs/`: architecture, workflow, design, and maintenance documentation.
- `.github/workflows/`: CI configuration.
- `Makefile`: top-level build/test helpers.
- `pyproject.toml`: Python package metadata and `axis` console script.
- `Axisfile`: default example container spec.
- `.axis/`: generated runtime state, ignored by convention and not committed.

## Python Package Layout

- `src/axis/cli.py`: CLI parser and command orchestration.
- `src/axis/axisfile.py`: `Axisfile` parser.
- `src/axis/config.py`: dataclasses representing user configuration.
- `src/axis/errors.py`: project exception types.
- `src/axis/image.py`: Docker image pull/export and rootfs copy support.
- `src/axis/network.py`: bridge/veth/IP/iptables setup and cleanup.
- `src/axis/ports.py`: port mapping parser and dataclass.
- `src/axis/process.py`: external command helpers.
- `src/axis/proxy.py`: TCP port proxy used for localhost publishing.
- `src/axis/runtime.py`: Python-to-C++ runtime config and subprocess management.
- `src/axis/state.py`: `.axis` state layout, lookup, inspect data, status, and PID helpers.

## C++ Runtime Layout

- `src/runtime/Container.cpp`: runtime entry point, `clone`, namespace setup, cgroup setup, bind mounts, `chroot`, `/proc`, env, and `execvp`.
- `src/runtime/runtime_config.hpp`: C++ runtime config struct.
- `src/runtime/runtime_config.cpp`: minimal JSON reader for the Python-generated runtime config.
- `src/runtime/Makefile`: builds `src/runtime/axis-runtime`.

## Placement Rules

- Add new CLI commands in `src/axis/cli.py` unless the command grows enough to justify a command module.
- Add new `Axisfile` directives in `src/axis/axisfile.py` and `src/axis/config.py`.
- Add generated per-container paths and state lookup behavior in `src/axis/state.py`.
- Add Docker/rootfs extraction behavior in `src/axis/image.py`.
- Add host/container network behavior in `src/axis/network.py` or `src/axis/proxy.py`.
- Add runtime syscall behavior in `src/runtime/Container.cpp`.
- Add new runtime JSON fields in both `src/axis/runtime.py` and `src/runtime/runtime_config.*` when C++ must consume them.

## Generated State

Do not commit `.axis/`. It may contain extracted image filesystems, logs, PIDs, network state, and copied `Axisfile`s.
