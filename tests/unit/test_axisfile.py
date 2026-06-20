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
                        "EXPOSE 8000",
                        "PORT 8080:8000",
                        "MEMORY 512M",
                        "CPU 100000 100000",
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
        self.assertEqual(config.command, ["python3", "app.py"])


if __name__ == "__main__":
    unittest.main()
