import os
import tempfile
import unittest
from pathlib import Path

from axis.network import allocate_ip, release_ip, read_network_state


class NetworkStateTests(unittest.TestCase):
    def test_allocate_reuse_and_release_ip(self):
        original_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                first = allocate_ip("demo-12345678")
                second = allocate_ip("demo-12345678")

                self.assertEqual(first, second)
                self.assertEqual(read_network_state()["allocations"]["demo-12345678"], str(first))

                release_ip("demo-12345678")
                self.assertNotIn("demo-12345678", read_network_state()["allocations"])
            finally:
                os.chdir(original_cwd)


if __name__ == "__main__":
    unittest.main()
