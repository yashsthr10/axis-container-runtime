# Axis Runtime

Axis is a small educational container runtime. It reads a Dockerfile-like `Axisfile`, snapshots a Docker image filesystem, starts a Linux namespace runtime, applies optional cgroup limits, creates Docker-style networking, and publishes requested ports on localhost.

## Example Axisfile

```dockerfile
FROM python:3.11-slim
NAME fastapi-demo
WORKDIR /
COPY examples/fastapi/app.py /app.py
EXPOSE 8000
PORT 8000:8000
MEMORY 512M
CPU 100000 100000
CMD python3 /app.py
```

## Usage

```bash
make build
sudo python3 -m axis.cli run
```

Then open:

```text
http://localhost:8000
```

## Developer Commands

```bash
make test
python3 -m axis.cli ps
python3 -m axis.cli clean <container-id>
```
