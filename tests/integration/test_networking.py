import os
import unittest


@unittest.skipUnless(os.geteuid() == 0, "requires root privileges")
class NetworkingIntegrationTests(unittest.TestCase):
    def test_placeholder_for_bridge_nat_and_port_publish(self):
        self.skipTest("integration flow requires root networking changes")


if __name__ == "__main__":
    unittest.main()
