# Examples

## Run The HTTP Example

Build the runtime:

```bash
make build
```

Run the example:

```bash
sudo PYTHONPATH=src python3 -m axis.cli run -f examples/fastapi/Axisfile
```

From another terminal, open:

```bash
curl http://localhost:8000
```

The app in `examples/fastapi/app.py` uses Python `http.server`, reads `/data/message.txt` from a bind mount, prints request logs to stdout, and responds:

```text
hello from axis
env=example
volume=message from the host bind mount
```

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

This example tests:

- `VOLUME ./data:/data`
- `ENV`
- `PORT 8000:8000`
- `MEMORY 512M`
- `CPU 100000 100000`
- captured request logs

## Inspect The Running Container

```bash
PYTHONPATH=src python3 -m axis.cli inspect fastapi-demo
```

Example output:

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

If more than one container has the same `NAME`, use the full generated ID from `axis ps`.

## Read Logs

After running `curl http://localhost:8000`, read the captured stdout/stderr:

```bash
PYTHONPATH=src python3 -m axis.cli logs fastapi-demo
```

Read cgroup stats:

```bash
PYTHONPATH=src python3 -m axis.cli stats fastapi-demo
```

Follow logs:

```bash
PYTHONPATH=src python3 -m axis.cli logs -f fastapi-demo
```

Logs are stored at:

```text
.axis/containers/<id>/logs.txt
```

You should see runtime startup output plus request logs like:

```text
AXIS_PID 12345
handled GET /
```

## Test Restart Policy

Use the dedicated restart example:

```bash
sudo PYTHONPATH=src python3 -m axis.cli run -f examples/restart/Axisfile
```

In another terminal, follow logs:

```bash
PYTHONPATH=src python3 -m axis.cli logs -f restart-demo
```

The command in `examples/restart/crash.py` prints, sleeps for two seconds, exits with code `1`, and is relaunched by the foreground restart loop.

Stop it from another terminal:

```bash
PYTHONPATH=src python3 -m axis.cli stop restart-demo
```

## Test Bind Volume

The FastAPI example includes:

```dockerfile
VOLUME ./data:/data
```

Host data lives at:

```text
examples/fastapi/data/message.txt
```

Change that file while the container is running:

```bash
printf 'updated from host\n' > examples/fastapi/data/message.txt
curl http://localhost:8000
```

The response should include:

```text
volume=updated from host
```

## Override CMD

Run an alternate command while keeping the same rootfs, ports, env, resources, and volumes:

```bash
sudo PYTHONPATH=src python3 -m axis.cli run -f examples/fastapi/Axisfile -- python3 -c "print(open('/data/message.txt').read())"
```

This is a quick smoke test for the bind mount without starting the HTTP server. Because the HTTP example does not set `RESTART always`, the command exits after printing the file.

## Clean Up

List containers:

```bash
PYTHONPATH=src python3 -m axis.cli ps
```

Reconcile stale runtime metadata:

```bash
PYTHONPATH=src python3 -m axis.cli reconcile
```

Stop running examples:

```bash
PYTHONPATH=src python3 -m axis.cli stop fastapi-demo
PYTHONPATH=src python3 -m axis.cli stop restart-demo
```

Remove state:

```bash
PYTHONPATH=src python3 -m axis.cli clean fastapi-demo
PYTHONPATH=src python3 -m axis.cli clean restart-demo
```

Remove bridge manually if needed:

```bash
make clean-net
```

## Minimal Manual Test Checklist

- `curl http://localhost:8000` shows the volume message.
- `axis inspect fastapi-demo` shows `status: running`, `memory: 512M`, IP, and `8000:8000`.
- `axis logs fastapi-demo` shows `handled GET /`.
- Editing `examples/fastapi/data/message.txt` changes the HTTP response.
- `axis logs -f restart-demo` shows repeated starts and exits.
- `axis stop restart-demo` stops the restart loop.
