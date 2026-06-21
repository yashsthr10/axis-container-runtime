# Modules

## Python Control Plane

### `axis.cli`

- **Path**: `src/axis/cli.py`
- **Purpose**: User-facing `axis` command.
- **Owns**: argparse setup, command dispatch, run lifecycle, restart loop, logs command, inspect command, stop/clean behavior.
- **Depends on**: parser, image, runtime, network, state.

### `axis.axisfile`

- **Path**: `src/axis/axisfile.py`
- **Purpose**: Parse Dockerfile-like `Axisfile` syntax into `AxisConfig`.
- **Owns**: instruction validation, quoted argument splitting, line-numbered config errors.
- **Depends on**: `axis.config`, `axis.ports`, `axis.errors`.

### `axis.config`

- **Path**: `src/axis/config.py`
- **Purpose**: Typed Python representation of container configuration.
- **Owns**: `AxisConfig`, `CopySpec`, `VolumeSpec`, `ResourceLimits`.
- **Depends on**: `pathlib.Path`, `axis.ports.PortMapping`.

### `axis.image`

- **Path**: `src/axis/image.py`
- **Purpose**: Convert Docker images plus `COPY` entries into a rootfs.
- **Owns**: `docker pull`, `docker create`, `docker export`, `docker rm`, rootfs path safety for `COPY`.
- **Depends on**: Docker CLI, `tar`, process helpers.

### `axis.runtime`

- **Path**: `src/axis/runtime.py`
- **Purpose**: Python side of the runtime boundary.
- **Owns**: `runtime.json` generation, runtime subprocess startup, `AXIS_PID` detection, teeing stdout/stderr to logs.
- **Depends on**: `src/runtime/axis-runtime`.

### `axis.state`

- **Path**: `src/axis/state.py`
- **Purpose**: File-backed runtime state.
- **Owns**: `.axis` directories, `ContainerState`, ID/name resolution, PID liveness, status, inspect payloads, container listing.
- **Depends on**: local filesystem and process table.

### `axis.network`

- **Path**: `src/axis/network.py`
- **Purpose**: Container networking.
- **Owns**: `axis0` bridge, IP allocation, veth pair setup, `nsenter` network config, forwarding/NAT rules, `/etc/hosts`, `/etc/resolv.conf`, network cleanup.
- **Depends on**: `ip`, `nsenter`, `sysctl`, `iptables`, `iptables-save`.

### `axis.proxy`

- **Path**: `src/axis/proxy.py`
- **Purpose**: Local TCP proxy for published ports.
- **Owns**: forwarding `127.0.0.1:<host>` to `<container_ip>:<container>`.
- **Depends on**: Python sockets and selectors.

### `axis.ports`

- **Path**: `src/axis/ports.py`
- **Purpose**: Parse and validate port mappings.
- **Owns**: `PortMapping`, TCP-only parsing, port-range validation.

### `axis.process`

- **Path**: `src/axis/process.py`
- **Purpose**: Small wrapper around external command execution.
- **Owns**: checked command execution and captured output behavior.

## C++ Runtime

### `src/runtime/Container.cpp`

- **Purpose**: Linux runtime executable.
- **Owns**: namespaces, cgroups, bind mounts, `chroot`, `/proc`, environment, command execution.
- **Depends on**: Linux syscalls and runtime config parser.

### `src/runtime/runtime_config.*`

- **Purpose**: Read Python-generated JSON into C++ structs.
- **Owns**: minimal string/string-array/string-map JSON parsing needed by Axis.
- **Depends on**: the JSON shape produced by `axis.runtime`.

## Test Modules

- `tests/unit/`: parser, runtime config, ports, and state helper tests.
- `tests/integration/`: root-gated placeholders for networking and runtime flows.
