# Design

This project is designed to make container runtime mechanics visible. Prefer direct, readable code over framework-heavy abstractions. The runtime is intentionally split into Python orchestration and C++ syscall execution so each language handles the part it is best suited for.

## Design Principles

- Keep the CLI user-facing and explicit. New runtime behavior should be discoverable through `Axisfile` syntax or `axis` subcommands.
- Keep Linux syscall work in `src/runtime/`. Python should not duplicate namespace, cgroup, or mount setup that belongs in the runtime binary.
- Keep orchestration in `src/axis/cli.py` and helper modules. C++ should not learn about Docker image pulls, Python proxy processes, or CLI restart policies.
- Persist generated details under `.axis/containers/<id>/`. Avoid hidden in-memory-only state for behavior that other commands need.
- Validate unsafe paths before they cross boundaries. Repeat critical validation in C++ when a failure could affect the host filesystem.

## User-Facing Interfaces

Axis has two main user-facing interfaces:

- `Axisfile`: declarative container configuration.
- `axis` CLI: imperative lifecycle commands.

`Axisfile` should stay Dockerfile-like and line-oriented. Parsing uses `shlex.split`, so quoting is supported. Unsupported instructions should fail fast with a line-numbered error.

CLI commands should return process-style exit codes and print concise human-readable errors through `AxisError`.

## Runtime Data Design

Per-container state lives under `.axis/containers/<id>/`:

- `Axisfile`: copy of the input file.
- `rootfs/`: exported Docker image filesystem plus `COPY` entries.
- `runtime.json`: Python-to-C++ contract.
- `pid`: latest host PID reported by the runtime.
- `network.json`: bridge/veth/IP/port proxy details.
- `logs.txt`: captured stdout/stderr.
- `status.json`: current status and restart/manual-stop hints.

The container ID format is `<name>-<8 hex chars>`. Commands may resolve either exact IDs or unique names.

## Error Design

- `AxisfileError` is for invalid user configuration.
- `AxisError` is for CLI/runtime orchestration failures.
- `CommandError` is for failed external commands.
- C++ runtime setup failures should print a clear stderr message and exit non-zero.

Avoid silent cleanup failures when they hide correctness issues. Cleanup paths may ignore missing processes or missing network devices because they are naturally idempotent.

## Restart Design

`RESTART always` is deliberately foreground-only. The Python `axis run` command owns the loop:

1. Start runtime.
2. Configure network and proxies.
3. Stream logs.
4. If the process exits and `manual_stop` is false, clean per-run network state and start again.

This avoids adding a daemon before the project needs one.

## Volume Design

`VOLUME ./data:/data` is a host bind mount. Python resolves the host path relative to the `Axisfile` directory and checks that it is an existing directory. C++ creates the rootfs target and calls `mount(..., MS_BIND | MS_REC, ...)` before `chroot`.

Directory-only volume support is intentional for now. File mounts would require more target-type handling.

## Testing Design

- Unit tests cover parsers, runtime JSON generation, and state helpers.
- C++ build warnings are treated seriously through `-Wall -Wextra -Wpedantic`.
- Integration tests are root-gated because networking, namespaces, cgroups, Docker image extraction, and iptables require elevated privileges.
