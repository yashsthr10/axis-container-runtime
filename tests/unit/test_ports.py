import unittest

from axis.errors import AxisfileError
from axis.ports import parse_port_mapping


class PortTests(unittest.TestCase):
    def test_host_and_container_mapping(self):
        mapping = parse_port_mapping("8080:8000")

        self.assertEqual(mapping.host, 8080)
        self.assertEqual(mapping.container, 8000)
        self.assertEqual(mapping.protocol, "tcp")

    def test_single_port_maps_to_same_container_port(self):
        mapping = parse_port_mapping("8000")

        self.assertEqual(mapping.host, 8000)
        self.assertEqual(mapping.container, 8000)

    def test_rejects_udp_for_now(self):
        with self.assertRaises(AxisfileError):
            parse_port_mapping("8000:8000/udp")


if __name__ == "__main__":
    unittest.main()
