import unittest
import os

from utils.client_detector import resolve_installation_paths


class TestClientPathDetection(unittest.TestCase):

    def test_resolve_installation_paths_returns_tuple(self):
        l_path, r_path = resolve_installation_paths()
        self.assertIsInstance(l_path, (str, type(None)))
        self.assertIsInstance(r_path, (str, type(None)))


if __name__ == "__main__":
    unittest.main()
