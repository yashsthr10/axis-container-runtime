import json
import tempfile
import unittest
from pathlib import Path

from axis.config import AxisConfig, ResourceLimits, VolumeSpec
from axis.ports import PortMapping
from axis.runtime import write_runtime_config
from axis.state import ContainerState


class RuntimeConfigTests(unittest.TestCase):
    def test_write_runtime_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            state = ContainerState(
                container_id="demo-12345678",
                name="demo",
                directory=directory,
                rootfs=directory / "rootfs",
                runtime_config=directory / "runtime.json",
                axisfile_copy=directory / "Axisfile",
                pid_file=directory / "pid",
                network_file=directory / "network.json",
                log_file=directory / "logs.txt",
                status_file=directory / "status.json",
                resource_file=directory / "resources.json",
                lock_file=directory / "container.lock",
            )
            state.rootfs.mkdir()
            volume_source = directory / "data"
            volume_source.mkdir()
            config = AxisConfig(
                image="python:3.11-slim",
                name="demo",
                command=["python3", "/app.py"],
                env={"APP_ENV": "dev"},
                volumes=[VolumeSpec(source=volume_source, destination="/data")],
                ports=[PortMapping(host=8080, container=8000)],
                resources=ResourceLimits(memory="512M", cpu="100000 100000"),
                restart="always",
            )

            write_runtime_config(config, state)
            runtime_config = json.loads(state.runtime_config.read_text())

        self.assertEqual(runtime_config["name"], "demo")
        self.assertEqual(runtime_config["hostname"], "demo")
        self.assertEqual(runtime_config["command"], ["python3", "/app.py"])
        self.assertEqual(runtime_config["env"]["APP_ENV"], "dev")
        self.assertEqual(runtime_config["ports"], ["8080:8000"])
        self.assertEqual(runtime_config["bind_mounts"], {"/data": str(volume_source)})
        self.assertEqual(runtime_config["restart"], "always")
        self.assertEqual(runtime_config["memory"], "512M")
        self.assertTrue(runtime_config["cgroup_path"].endswith("/demo-12345678"))


if __name__ == "__main__":
    unittest.main()
