# Workflow

This file describes operator workflows: the commands people run and the side effects they should expect.

## WF-001: Build The Runtime

- **Trigger**: `make build`
- **Entry point**: top-level `Makefile`
- **Steps**:
  1. Invoke `make -C src/runtime`.
  2. Compile `Container.cpp` and `runtime_config.cpp`.
  3. Write `src/runtime/axis-runtime`.
- **State touched**: `src/runtime/axis-runtime`.
- **Failure path**: C++ compiler errors or missing compiler.

## WF-002: Run A Container

- **Trigger**: `sudo PYTHONPATH=src python3 -m axis.cli run -f examples/fastapi/Axisfile`
- **Entry point**: `axis.cli.run_command`
- **Pre-checks**:
  - Must run as root.
  - `Axisfile` must exist and include `FROM` and `CMD`, unless a CLI command override is supplied.
  - `src/runtime/axis-runtime` must exist.
  - Docker, `ip`, `nsenter`, and iptables tools must be available for the full flow.
- **Steps**:
  1. Parse config.
  2. Create state directory.
  3. Prepare rootfs from Docker image.
  4. Start runtime.
  5. Configure network and proxies.
  6. Stream container logs to terminal and `logs.txt`.
  7. Keep state after exit for `inspect` and `logs`.
- **Exit path**: returns the container process exit code.
- **Failure path**: raises `AxisError`, `AxisfileError`, or `CommandError`; CLI prints `axis: ...`.

## WF-003: Run With Command Override

- **Trigger**: `sudo axis run -f Axisfile -- python3 /other.py`
- **Behavior**:
  - Arguments after `--` replace the `CMD` instruction.
  - The rest of the `Axisfile` still applies.
  - This is useful for debugging an image or testing alternate commands.

## WF-004: Inspect A Container

- **Trigger**: `axis inspect fastapi-demo`
- **Entry point**: `inspect_command`
- **Steps**:
  1. Resolve `fastapi-demo` as exact ID or unique container name.
  2. Read runtime, status, PID, and network state.
  3. Print JSON.
- **Example output**:

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

## WF-005: Read Logs

- **Trigger**: `axis logs fastapi-demo`
- **Entry point**: `logs_command`
- **Behavior**:
  - Prints the captured combined stdout/stderr from `logs.txt`.
  - `axis logs -f fastapi-demo` follows new lines.
  - Logs include runtime setup output such as `AXIS_PID <pid>` as well as container process output.

## WF-006: Stop A Container

- **Trigger**: `axis stop fastapi-demo`
- **Entry point**: `stop_command`
- **Behavior**:
  - Resolves exact ID or unique name.
  - Marks `manual_stop=true`.
  - Sends `SIGTERM` to the stored PID.
  - Marks status as `stopped`.
  - Prevents a foreground `RESTART always` loop from relaunching.

## WF-007: Clean Container State

- **Trigger**: `axis clean fastapi-demo`
- **Entry point**: `clean_command`
- **Behavior**:
  - Stops proxy processes.
  - Cleans network artifacts.
  - Terminates recorded PID if present.
  - Removes `.axis/containers/<id>/`.
- **Note**: IP allocations in `.axis/networks/axis0.json` can remain allocated by container ID.

## WF-008: Develop And Test

- **Unit tests**: `make test`
- **Full discovery**: `python3 -m unittest discover`
- **Build check**: `make build`
- **CI**:
  1. Install Python package editable.
  2. Build runtime.
  3. Run unit tests.
  4. Run full test discovery.

Integration tests are root-gated and currently skip the expensive Docker/network runtime path.
