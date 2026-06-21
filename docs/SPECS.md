# Specifications

## Objective

Axis should let a developer run a simple container from a Docker image using an `Axisfile`, inspect its state, read logs, publish ports, apply basic resource limits, restart on failure, and bind mount host directories.

## Supported CLI Commands

### `axis run`

```bash
sudo axis run [-f Axisfile] [-- command args...]
```

Requirements:

- Must run as root.
- Defaults to `Axisfile` in the current working directory.
- Creates a new container state directory each run.
- CLI command override replaces `CMD` when provided after `--`.
- Streams runtime stdout/stderr to terminal and `logs.txt`.
- Keeps state after normal exit.

### `axis ps`

Lists known containers from `.axis/containers`.

Columns:

- `ID`
- `NAME`
- `PID`
- `ROOTFS`

PID is shown only if it appears live.

### `axis stop <container>`

Stops by exact container ID or unique name.

Behavior:

- Accepts `--timeout`, defaulting to 30 seconds.
- Resolves exact container ID or unique name.
- Writes `manual_stop=true`.
- Transitions the container toward `stopping`.
- Uses cgroup process ownership when available.
- Sends `SIGTERM`, waits, and escalates to `SIGKILL` if needed.
- Does not restart containers stopped manually.
- Succeeds for already-exited containers.

### `axis inspect <container>`

Prints JSON:

```json
{
  "id": "fastapi-demo-12345678",
  "pid": 12345,
  "ip": "10.88.0.2",
  "ports": ["8000:8000"],
  "memory": "512M",
  "status": "running"
}
```

Resolution rules:

- Exact container ID wins.
- Otherwise match by `runtime.json.name`.
- Duplicate names are rejected as ambiguous.

### `axis logs <container> [-f]`

Prints captured combined stdout/stderr.

- Without `--follow`, prints existing `logs.txt` and exits.
- With `--follow`, polls the file for new lines.

### `axis stats <container>`

Prints cgroup v2 resource counters when the container cgroup exists.

Fields may include:

- `memory_current`
- `memory_peak`
- `memory_max`
- `memory_events`
- `cpu_stat`
- `pids_current`
- `pids_max`
- `cgroup_events`
- `io_stat`

### `axis reconcile`

Scans persisted state and repairs simple stale metadata, such as dead running PIDs and stale proxy PID entries.

If `.axis` state is root-owned and the command is not run as root, reconcile reports repairs that require root instead of crashing.

### `axis clean <container>`

Removes a known container state directory after best-effort runtime/network cleanup.

Cleanup uses persisted ownership metadata when available and is intended to be idempotent for missing processes, missing veths, already-released IPs, and already-removed state.

## Runtime State And Ownership

Per-container state lives under `.axis/containers/<id>/`.

Important files:

- `status.json`: lifecycle state, desired state, timestamps, exit details, restart count, and manual stop intent.
- `resources.json`: owned resources such as rootfs, cgroup path, veth, IP allocation, proxy PIDs, and bind mounts.
- `runtime.json`: Python-to-C++ runtime contract.
- `network.json`: bridge, veth, IP, ports, and proxy metadata.
- `logs.txt`: combined runtime stdout/stderr.

Lifecycle states:

- `created`
- `starting`
- `running`
- `stopping`
- `exited`
- `failed`
- `deleted`

State writes should be atomic and transitions should be validated.

## Supported Axisfile Instructions

### `FROM <image>`

Required. Docker image used to prepare the rootfs.

### `NAME <name>`

Optional. Defaults to `axis-container`. Used as runtime name, hostname fallback, and prefix for generated container IDs.

### `HOSTNAME <hostname>`

Optional. Defaults to `NAME`.

### `WORKDIR <path>`

Optional. Defaults to `/`. Passed to C++ runtime after `chroot`.

### `COPY <source> <destination>`

Copies from host into rootfs after Docker image export.

- Source is resolved relative to the `Axisfile` directory.
- Destination must stay inside rootfs.
- Directories and files are supported.

### `VOLUME <source>:<destination>`

Bind mounts a host directory into the container.

- Source is resolved relative to the `Axisfile` directory.
- Source must be an existing directory.
- Destination must be absolute.
- Destination cannot be `/`.
- Destination cannot include parent traversal that escapes rootfs.

### `ENV KEY=VALUE`

Adds an environment variable. Key cannot be empty.

### `EXPOSE <port>`

Records an exposed port in config. It is currently informational and does not publish the port by itself.

### `PORT <host>:<container>`

Publishes a TCP port through a Python localhost proxy.

Also supports `PORT <port>`, meaning host and container port are the same.

Only TCP is supported. UDP mappings are rejected.

### `MEMORY <limit>`

Passed to cgroup v2 `memory.max`.

Example: `MEMORY 512M`.

### `CPU <quota period>`

Passed to cgroup v2 `cpu.max`.

Example: `CPU 100000 100000`.

### `RESTART always`

Enables foreground restart supervision.

- Only `always` is supported.
- Restarts happen while `axis run` is still running.
- `axis stop` or Ctrl-C marks manual stop and prevents another restart.

### `CMD <command args...>`

Required unless a CLI command override is provided.

Parsing uses `shlex.split`, so quoted arguments are supported.

## Functional Requirements

- Axis must prepare a rootfs from Docker images.
- Axis must isolate the container process with PID, mount, UTS, and network namespaces.
- Axis must support cgroup memory and CPU limits.
- Axis must publish localhost TCP ports.
- Axis must persist enough state for `ps`, `stop`, `inspect`, `logs`, and `clean`.
- Axis must capture runtime stdout/stderr.
- Axis must support bind-mounting host directories.
- Axis must restart containers configured with `RESTART always` while `axis run` remains attached.
- Axis must expose cgroup stats through `axis stats`.
- Axis must distinguish common exit reasons such as completed, error, signal, stopped, stale PID, and OOM kill when information is available.
- Axis must support explicit reconciliation for stale PID and proxy metadata.

## Constraints

- Linux only.
- Root required for `axis run`.
- Docker CLI required for image preparation.
- No daemon process.
- `RESTART always` remains foreground-only until `axisd` exists.
- No OCI image/runtime compatibility claim.
- Runtime JSON parser is intentionally minimal and expects the shape Python writes.

## Remaining Production Work

- Make cleanup entirely resource-journal driven, including partial network setup rollback.
- Expand cgroup cleanup and stats tests with root-gated integration cases.
- Add OOM-specific integration tests and persist final cgroup counters before cgroup removal.
- Make proxy readiness checks deterministic instead of sleep-based.
- Add `axis reconcile --repair` for leaked veths, proxies, and stale IP allocations.
- Add privileged CI or a manual integration suite for namespaces, cgroups, iptables, and OOM behavior.
- Introduce `axisd` only after lifecycle, resource ownership, cleanup, and reconciliation are stable.

## Acceptance Checks

- `make build` builds `src/runtime/axis-runtime`.
- `make test` passes unit tests.
- `axis inspect <name>` works for a unique container name.
- `axis logs <name>` prints captured runtime/container output.
- `axis stats <name>` prints cgroup counters when the cgroup exists.
- `axis reconcile` exits cleanly and reports stale metadata repairs or root-required repairs.
- `RESTART always` relaunches after process exit until manual stop.
- `VOLUME ./data:/data` appears inside the container when the host directory exists.
