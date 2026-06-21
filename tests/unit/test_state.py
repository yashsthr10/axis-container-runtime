import os
import tempfile
import unittest
from pathlib import Path

from axis.errors import AxisError
from axis.state import (
    add_resource,
    inspect_container,
    read_resources,
    resolve_container,
    transition_state,
    write_json,
    write_status,
)


class StateTests(unittest.TestCase):
    def test_resolve_by_unique_name_and_inspect(self):
        original_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                container_dir = Path(".axis/containers/demo-12345678")
                container_dir.mkdir(parents=True)
                write_json(
                    container_dir / "runtime.json",
                    {
                        "name": "demo",
                        "memory": "512M",
                        "ports": ["8080:8000"],
                    },
                )
                write_json(
                    container_dir / "network.json",
                    {
                        "container_ip": "10.88.0.2",
                        "ports": [{"host": 8080, "container": 8000, "protocol": "tcp"}],
                    },
                )
                write_status(resolve_container("demo"), "exited", exit_code=0)

                state = resolve_container("demo")
                inspected = inspect_container("demo")
            finally:
                os.chdir(original_cwd)

        self.assertEqual(state.container_id, "demo-12345678")
        self.assertEqual(inspected["id"], "demo-12345678")
        self.assertEqual(inspected["ip"], "10.88.0.2")
        self.assertEqual(inspected["ports"], ["8080:8000"])
        self.assertEqual(inspected["memory"], "512M")
        self.assertEqual(inspected["status"], "exited")

    def test_validates_state_transitions(self):
        original_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                container_dir = Path(".axis/containers/demo-12345678")
                container_dir.mkdir(parents=True)
                write_json(container_dir / "runtime.json", {"name": "demo"})
                state = resolve_container("demo")

                transition_state(state, "starting")
                transition_state(state, "running", pid=123)

                with self.assertRaises(AxisError):
                    transition_state(state, "created")
            finally:
                os.chdir(original_cwd)

    def test_records_owned_resources_once(self):
        original_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                container_dir = Path(".axis/containers/demo-12345678")
                container_dir.mkdir(parents=True)
                write_json(container_dir / "runtime.json", {"name": "demo"})
                state = resolve_container("demo")
                resource = {"type": "rootfs", "path": ".axis/containers/demo-12345678/rootfs"}

                add_resource(state, resource)
                add_resource(state, resource)
                resources = read_resources(state)
            finally:
                os.chdir(original_cwd)

        self.assertEqual(resources, [resource])


if __name__ == "__main__":
    unittest.main()
