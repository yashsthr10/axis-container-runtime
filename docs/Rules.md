# Rules

## Runtime Boundary Rules

- Python calls C++ through `src/runtime/axis-runtime` as a subprocess.
- Do not introduce Cython, `ctypes`, or a native Python extension unless `Decisions.md` is updated.
- Any C++-consumed `runtime.json` field must be documented and tested from the Python writer side.
- Keep CLI policy in Python unless there is a strong syscall-level reason to move it into C++.

## Axisfile Rules

- Every new instruction needs parser validation and unit tests.
- Error messages for invalid instructions should include the line number.
- Host paths should be resolved relative to the `Axisfile` directory.
- Container paths must not escape the rootfs.
- Unsupported behavior should fail fast instead of being ignored.

## State Rules

- Generated state belongs under `.axis/`.
- Do not commit `.axis/`, extracted rootfs files, logs, PIDs, or network state.
- Commands should use `state.py` helpers instead of reconstructing `.axis` paths repeatedly.
- Commands accepting a container reference should support exact ID and unique name unless there is a reason not to.

## Linux Safety Rules

- `axis run` must require root while it manages namespaces, cgroups, mounts, veth pairs, routes, and iptables.
- Validate bind mount destinations before calling `mount`.
- Keep cleanup idempotent for naturally missing resources.
- Do not silently ignore setup failures that leave the container partially configured.

## Testing Rules

- Rootless unit tests should cover parser, state, runtime JSON, and small helpers.
- Changes to C++ runtime config require `make build`.
- Network/runtime integration tests must be root-gated.
- User-facing behavior changes should update examples and specs.

## Documentation Rules

- Update `SPECS.md` for CLI or `Axisfile` syntax changes.
- Update `Codepath.md` for lifecycle changes.
- Update `LLD.md` for state or runtime JSON schema changes.
- Update `Decisions.md` when changing a major boundary or trade-off.
