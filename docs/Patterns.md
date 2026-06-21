# Patterns

## CLI Command Pattern

Used in `src/axis/cli.py`.

Structure:

1. Add an argparse subparser in `main`.
2. Dispatch by `args.command_name`.
3. Implement a `*_command` function that returns an integer exit code.
4. Raise `AxisError` for user-facing failures.
5. Let `main` print `axis: <message>` to stderr.

Use this for `ps`, `stop`, `inspect`, `logs`, and `clean`.

## Axisfile Directive Pattern

Used in `src/axis/axisfile.py` and `src/axis/config.py`.

Structure:

1. Add a dataclass field if the config needs new state.
2. Add parser state variables near the top of `parse_axisfile`.
3. Add an `elif instruction == ...` branch.
4. Validate with line numbers.
5. Include the parsed value in `AxisConfig`.
6. Add unit tests.
7. Update `SPECS.md` and examples.

Use this for user-facing configuration such as `VOLUME` and `RESTART`.

## Runtime JSON Boundary Pattern

Used by `src/axis/runtime.py` and `src/runtime/runtime_config.*`.

Structure:

1. Python serializes a simple JSON field.
2. C++ parser adds a matching field only if the runtime must consume it.
3. Keep JSON shapes simple: strings, string arrays, and string maps.
4. Add Python unit tests for generated JSON.
5. Build the C++ runtime after changing the parser.

Do not add complex nested JSON unless the C++ parser is upgraded intentionally.

## File-Backed State Pattern

Used in `src/axis/state.py`.

Structure:

1. Keep generated state under `.axis/containers/<id>/`.
2. Add paths to `ContainerState`.
3. Provide helper functions for reading/writing state.
4. Resolve containers by exact ID first, then unique name.
5. Avoid scattering path construction across commands.

Use this for `pid`, `network.json`, `logs.txt`, `status.json`, and future inspectable metadata.

## Best-Effort Cleanup Pattern

Used in `src/axis/cli.py` and `src/axis/network.py`.

Allowed idempotent failures:

- Killing a process that already exited.
- Deleting a veth that no longer exists.
- Removing iptables rules that are not present.

Still raise on setup failures that prevent a container from running correctly.

## Root-Gated Integration Pattern

Used in `tests/integration`.

Integration tests that need namespaces, Docker, cgroups, or network changes should be guarded with:

```python
@unittest.skipUnless(os.geteuid() == 0, "requires root privileges")
```

Unit tests should remain rootless and fast.
