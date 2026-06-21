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

- Reads the stored PID.
- Writes `manual_stop=true`.
- Sends `SIGTERM`.
- Marks status `stopped`.

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

### `axis clean <container>`

Removes a known container state directory after best-effort runtime/network cleanup.

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

## Constraints

- Linux only.
- Root required for `axis run`.
- Docker CLI required for image preparation.
- No daemon process.
- No OCI image/runtime compatibility claim.
- Runtime JSON parser is intentionally minimal and expects the shape Python writes.

## Acceptance Checks

- `make build` builds `src/runtime/axis-runtime`.
- `make test` passes unit tests.
- `axis inspect <name>` works for a unique container name.
- `axis logs <name>` prints captured runtime/container output.
- `RESTART always` relaunches after process exit until manual stop.
- `VOLUME ./data:/data` appears inside the container when the host directory exists.
