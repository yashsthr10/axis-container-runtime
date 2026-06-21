import tempfile
import unittest
from pathlib import Path

from axis.cli import exit_details_from_code, read_cgroup_stats


class CliHelperTests(unittest.TestCase):
    def test_read_cgroup_stats_parses_flat_and_key_value_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            cgroup = Path(tmp)
            (cgroup / "memory.current").write_text("1024\n")
            (cgroup / "memory.max").write_text("2048\n")
            (cgroup / "memory.events").write_text("low 0\noom 1\noom_kill 1\n")
            (cgroup / "cpu.stat").write_text("usage_usec 123\nsystem_usec 45\n")

            stats = read_cgroup_stats(cgroup)

        self.assertTrue(stats["available"])
        self.assertEqual(stats["memory_current"], "1024")
        self.assertEqual(stats["memory_max"], "2048")
        self.assertEqual(stats["memory_events"]["oom_kill"], 1)
        self.assertEqual(stats["cpu_stat"]["usage_usec"], 123)

    def test_exit_details_detect_oom_signal_and_success(self):
        oom = exit_details_from_code(137, {"memory_events": {"oom_kill": 1}})
        signaled = exit_details_from_code(143, {"memory_events": {"oom_kill": 0}})
        completed = exit_details_from_code(0, {})

        self.assertEqual(oom["exit_reason"], "oom_killed")
        self.assertTrue(oom["oom_killed"])
        self.assertEqual(signaled["exit_reason"], "signal")
        self.assertEqual(signaled["exit_signal"], 15)
        self.assertEqual(completed["exit_reason"], "completed")


if __name__ == "__main__":
    unittest.main()
