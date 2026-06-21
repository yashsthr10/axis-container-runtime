# Contributing

## Development Setup

Build the C++ runtime:

```bash
make build
```

Run unit tests:

```bash
make test
PYTHONPATH=src python3 -m unittest discover
```

Format Python code and view unit test coverage:

```bash
make format
make coverage
```

Run the example container:

```bash
sudo PYTHONPATH=src python3 -m axis.cli run -f examples/fastapi/Axisfile
```

## Notes

- Do not commit generated runtime state from `.axis/`.
- Do not commit extracted filesystems from `rootfs/`.
- Runtime and networking integration tests require root privileges.
- Keep user-facing container configuration in `Axisfile`; generated runtime details belong under `.axis/`.
