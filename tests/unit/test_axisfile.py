import tempfile
import unittest
from pathlib import Path

from axis.axisfile import parse_axisfile


class AxisfileTests(unittest.TestCase):
    def test_parse_axisfile(self):
        with tempfile.TemporaryDirectory() as tmp:
            axisfile = Path(tmp) / "Axisfile"
            axisfile.write_text(
                "\n".join(
                    [
                        "FROM python:3.11-slim",
                        "NAME demo",
                        "WORKDIR /app",
                        "ENV APP_ENV=dev",
                        "COPY . /app",
                        "VOLUME ./data:/data",
                        "EXPOSE 8000",
                        "PORT 8080:8000",
                        "MEMORY 512M",
                        "CPU 100000 100000",
                        "RESTART always",
                        "CMD python3 app.py",
                    ]
                )
            )

            config = parse_axisfile(axisfile)

        self.assertEqual(config.image, "python:3.11-slim")
        self.assertEqual(config.name, "demo")
        self.assertEqual(config.workdir, "/app")
        self.assertEqual(config.env["APP_ENV"], "dev")
        self.assertEqual(config.ports[0].host, 8080)
        self.assertEqual(config.ports[0].container, 8000)
        self.assertEqual(config.resources.memory, "512M")
        self.assertEqual(config.resources.cpu, "100000 100000")
        self.assertEqual(config.restart, "always")
        self.assertEqual(config.volumes[0].source, (axisfile.parent / "data").resolve())
        self.assertEqual(config.volumes[0].destination, "/data")
        self.assertEqual(config.command, ["python3", "app.py"])

    def test_rejects_invalid_volume_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            axisfile = Path(tmp) / "Axisfile"
            axisfile.write_text(
                "\n".join(
                    [
                        "FROM python:3.11-slim",
                        "VOLUME ./data:data",
                        "CMD python3 app.py",
                    ]
                )
            )

            with self.assertRaisesRegex(Exception, "destination must be an absolute path"):
                parse_axisfile(axisfile)

    def test_rejects_unsupported_restart_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            axisfile = Path(tmp) / "Axisfile"
            axisfile.write_text(
                "\n".join(
                    [
                        "FROM python:3.11-slim",
                        "RESTART on-failure",
                        "CMD python3 app.py",
                    ]
                )
            )

            with self.assertRaisesRegex(Exception, "unsupported RESTART policy"):
                parse_axisfile(axisfile)


if __name__ == "__main__":
    unittest.main()
