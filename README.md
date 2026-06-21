# Axis Runtime

Axis is a small educational container runtime. It reads a Dockerfile-like `Axisfile`, snapshots a Docker image filesystem, starts a Linux namespace runtime, applies optional cgroup limits, creates Docker-style networking, and publishes requested ports on localhost.

## Example Axisfile

```dockerfile
FROM python:3.11-slim
NAME fastapi-demo
WORKDIR /
COPY app.py /app.py
VOLUME ./data:/data
ENV APP_ENV=example
EXPOSE 8000
PORT 8000:8000
MEMORY 512M
CPU 100000 100000
CMD python3 /app.py
```

## Usage

```bash
make build
sudo PYTHONPATH=src python3 -m axis.cli run -f examples/fastapi/Axisfile
```

Then test the HTTP server and bind mount:

```bash
curl http://localhost:8000
PYTHONPATH=src python3 -m axis.cli inspect fastapi-demo
PYTHONPATH=src python3 -m axis.cli logs fastapi-demo
```

Test restart policy with the crash-loop example:

```bash
sudo PYTHONPATH=src python3 -m axis.cli run -f examples/restart/Axisfile
PYTHONPATH=src python3 -m axis.cli logs -f restart-demo
PYTHONPATH=src python3 -m axis.cli stop restart-demo
```

## Developer Commands

```bash
make test
PYTHONPATH=src python3 -m axis.cli ps
PYTHONPATH=src python3 -m axis.cli stop <container>
PYTHONPATH=src python3 -m axis.cli clean <container>
```
