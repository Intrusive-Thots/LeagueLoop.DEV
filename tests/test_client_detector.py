import unittest
from unittest.mock import patch, mock_open
import os
import sys
import json

from utils.client_detector import (
    resolve_installation_paths,
    get_league_lockfile,
    get_riot_lockfile,
    scan_clients
)

class TestClientDetector(unittest.TestCase):

    @patch("os.path.getsize")
    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data='{"rc_default": "C:/Riot Games/Riot Client/RiotClientServices.exe", "associated_client": {"C:/Riot Games/League of Legends/": ""}}')
    def test_resolve_installation_paths(self, mock_file, mock_exists, mock_getsize):
        # Setup mocks
        mock_exists.return_value = True
        mock_getsize.return_value = 100  # Mock file size > 2

        # Run method (force re-evaluation by resetting internal module state if necessary, 
        # but since we run it first, it's fine)
        import utils.client_detector
        utils.client_detector._paths_resolved = False
        utils.client_detector._league_install_path = None
        utils.client_detector._riot_install_path = None

        league, riot = resolve_installation_paths()
        
        self.assertEqual(riot, os.path.normpath("C:/Riot Games/Riot Client"))
        self.assertEqual(league, os.path.normpath("C:/Riot Games/League of Legends/"))

    @patch("os.path.getsize")
    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data="LeagueClient:12345:8888:token:https")
    def test_get_league_lockfile(self, mock_file, mock_exists, mock_getsize):
        mock_exists.return_value = True
        mock_getsize.return_value = 100  # Mock file size > 2
        
        import utils.client_detector
        utils.client_detector._league_install_path = "C:\\Riot Games\\League of Legends"

        port, token = get_league_lockfile()
        self.assertEqual(port, "8888")
        self.assertEqual(token, "token")

    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data="RiotClient:1111:9999:riottoken:https")
    def test_get_riot_lockfile(self, mock_file, mock_exists):
        mock_exists.return_value = True
        
        port, token = get_riot_lockfile()
        self.assertEqual(port, "9999")
        self.assertEqual(token, "riottoken")

    @patch("psutil.process_iter")
    def test_scan_clients(self, mock_process_iter):
        # Mock running processes
        class MockProcessInfo:
            def __init__(self, pid, name, cmdline):
                self.pid = pid
                self._name = name
                self._cmdline = cmdline
                self.info = {"pid": pid, "name": name}

            def name(self):
                return self._name

            def cmdline(self):
                return self._cmdline

        p1 = MockProcessInfo(100, "LeagueClient.exe", ["--app-port=1234", "--remoting-auth-token=abc"])
        p2 = MockProcessInfo(200, "RiotClientServices.exe", ["--app-port=5678", "--remoting-auth-token=xyz"])
        
        mock_process_iter.return_value = [p1, p2]

        # Scan
        import utils.client_detector
        # Set scan time back to bypass cache
        utils.client_detector._last_scan_time = 0.0

        results = scan_clients()

        self.assertTrue(results["league"]["connected"])
        self.assertEqual(results["league"]["port"], "1234")
        self.assertEqual(results["league"]["token"], "abc")
        self.assertEqual(results["league"]["pid"], 100)

        self.assertTrue(results["riot"]["connected"])
        self.assertEqual(results["riot"]["port"], "5678")
        self.assertEqual(results["riot"]["token"], "xyz")
        self.assertEqual(results["riot"]["pid"], 200)

if __name__ == "__main__":
    unittest.main()
