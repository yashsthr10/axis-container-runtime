# Code Paths

This file documents the main execution paths through Axis.

## CP-001: `axis run`

- **Trigger**: `sudo axis run [-f Axisfile] [-- command ...]`
- **Entry point**: `axis.cli.main()` -> `run_command()`
- **Core steps**:
  1. Require root with `os.geteuid()`.
  2. Initialize `.axis/images`, `.axis/containers`, and `.axis/networks`.
  3. Parse `Axisfile` with optional command override.
  4. Create `.axis/containers/<name>-<uuid>/`.
  5. Copy the input `Axisfile` into container state.
  6. Pull/create/export/remove Docker image container into `rootfs/`.
  7. Apply `COPY` entries into the rootfs.
  8. Write `runtime.json`.
  9. Initialize `logs.txt` and `status.json`.
  10. Enter `run_container_loop()`.
- **Exit points**:
  - Returns the container command exit code for non-restart containers.
  - Returns `130` after Ctrl-C cleanup.
  - Continues indefinitely for `RESTART always` until manually stopped or interrupted.
- **Failure points**:
  - Missing `Axisfile`.
  - Invalid directive.
  - Missing `src/runtime/axis-runtime`.
  - Docker pull/export failure.
  - Volume source missing or not a directory.
  - Root/network/cgroup/mount permission failures.

## CP-002: Runtime Launch

- **Trigger**: `run_container_once()`
- **Entry point**: `axis.runtime.start_runtime()`
- **Core steps**:
  1. Start `src/runtime/axis-runtime <runtime.json>` with stdout and stderr merged.
  2. Tee runtime output to terminal and `logs.txt`.
  3. Wait for `AXIS_PID <pid>`.
  4. Write the host PID to `.axis/containers/<id>/pid`.
  5. Mark status as `running`.
- **Failure points**:
  - Runtime binary missing.
  - C++ runtime exits before reporting `AXIS_PID`.
  - Invalid runtime JSON.
  - C++ setup failure before PID report.

## CP-003: C++ Runtime Setup

- **Trigger**: `src/runtime/axis-runtime runtime.json`
- **Entry point**: `src/runtime/Container.cpp::main`
- **Core steps**:
  1. Parse runtime JSON through `loadRuntimeConfig()`.
  2. Create sync pipe.
  3. `clone()` child with `CLONE_NEWPID`, `CLONE_NEWNS`, `CLONE_NEWUTS`, `CLONE_NEWNET`, and `SIGCHLD`.
  4. Print `AXIS_PID <pid>`.
  5. Parent creates cgroup path and writes memory/CPU limits.
  6. Parent writes child PID to `cgroup.procs`.
  7. Parent releases child through the sync pipe.
  8. Child sets hostname.
  9. Child makes mount propagation private.
  10. Child bind mounts configured volumes into the rootfs.
  11. Child `chroot`s and changes workdir.
  12. Child mounts `/proc`.
  13. Child applies environment variables and `execvp()`s the command.
  14. Parent waits for child and returns the child exit code.
- **Failure points**:
  - `clone`, `pipe`, cgroup file writes, bind mount, `chroot`, `/proc` mount, or `execvp` can fail.

## CP-004: Network Setup

- **Trigger**: Python receives `AXIS_PID`.
- **Entry point**: `axis.network.setup_network()`
- **Core steps**:
  1. Ensure bridge `axis0`.
  2. Allocate/reuse an IP in `10.88.0.0/24`.
  3. Create veth pair using the container ID suffix.
  4. Attach host veth to `axis0`.
  5. Move container veth into the container network namespace.
  6. Configure container IP, loopback, and default route through `nsenter`.
  7. Enable host IP forwarding.
  8. Ensure NAT/forwarding iptables rules.
  9. Write `resolv.conf` and `hosts` into rootfs.
  10. Start Python proxy processes for published ports.
  11. Write `network.json`.
- **Failure points**:
  - Missing `ip`, `nsenter`, `iptables`, or root privileges.
  - Port already in use on `127.0.0.1`.
  - Container process exits before network setup finishes.

## CP-005: Logs

- **Trigger**: `axis logs <container> [-f]`
- **Entry point**: `logs_command()`
- **Core steps**:
  1. Resolve exact ID or unique name.
  2. Open `.axis/containers/<id>/logs.txt`.
  3. Print existing lines.
  4. If `--follow`, keep polling for new lines every 0.5 seconds.
- **Failure points**:
  - Unknown container.
  - Missing log file.

## CP-006: Inspect

- **Trigger**: `axis inspect <container>`
- **Entry point**: `inspect_command()` -> `state.inspect_container()`
- **Core steps**:
  1. Resolve exact ID or unique name.
  2. Read `runtime.json`.
  3. Read `status.json` if present.
  4. Read `pid` and check liveness with `os.kill(pid, 0)`.
  5. Read `network.json` if present.
  6. Build JSON with `id`, `pid`, `ip`, `ports`, `memory`, and `status`.
- **Failure points**:
  - Unknown container.
  - Ambiguous name.
  - Corrupt state JSON.

## CP-007: Stop And Clean

- **Stop trigger**: `axis stop <container>`
- **Stop path**:
  1. Resolve exact ID or unique name.
  2. Read PID.
  3. Mark `manual_stop=true`.
  4. Send `SIGTERM`.
  5. Mark status `stopped`.

- **Clean trigger**: `axis clean <container>`
- **Clean path**:
  1. Resolve exact ID or unique name.
  2. Terminate port proxy PIDs from `network.json`.
  3. Delete host veth and port rules through network cleanup.
  4. Terminate recorded container PID if present.
  5. Remove `.axis/containers/<id>/`.
