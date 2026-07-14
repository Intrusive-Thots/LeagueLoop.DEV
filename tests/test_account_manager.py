import unittest
from unittest.mock import patch, MagicMock
import os
import sys

from services.account_manager import AccountManager

class TestAccountManager(unittest.TestCase):

    @patch("services.account_manager.win32crypt")
    @patch.object(AccountManager, "_load")
    @patch.object(AccountManager, "_save")
    def test_default_account_operations(self, mock_save, mock_load, mock_win32crypt):
        # Setup mocks
        mock_win32crypt.CryptProtectData.return_value = b"encrypted"
        mock_win32crypt.CryptUnprotectData.return_value = (None, b"decrypted")

        # Initialize AccountManager
        mgr = AccountManager()
        
        # Test adding accounts
        idx1 = mgr.add_account("Account 1", "user1", "pass1", "Riot1#NA1")
        idx2 = mgr.add_account("Account 2", "user2", "pass2", "Riot2#NA1")

        self.assertEqual(idx1, 0)
        self.assertEqual(idx2, 1)

        # Test initial default status (should be False)
        self.assertEqual(mgr.get_default_account_index(), -1)

        # Set default to index 1
        mgr.set_default_account(idx2)
        self.assertEqual(mgr.get_default_account_index(), 1)
        self.assertTrue(mgr.get_accounts()[1]["is_default"])
        self.assertFalse(mgr.get_accounts()[0]["is_default"])

        # Edit account default status
        mgr.edit_account(idx1, is_default=True)
        self.assertEqual(mgr.get_default_account_index(), 0)
        self.assertTrue(mgr.get_accounts()[0]["is_default"])
        self.assertFalse(mgr.get_accounts()[1]["is_default"])

    @patch("services.account_manager.win32crypt")
    @patch("services.account_manager.scan_clients")
    @patch.object(AccountManager, "_load")
    @patch.object(AccountManager, "_save")
    def test_auto_populate_logged_in_account(self, mock_save, mock_load, mock_scan, mock_win32crypt):
        def encrypt_side_effect(data, *args, **kwargs):
            return b"enc_empty" if data == b"" else b"enc_val"
            
        def decrypt_side_effect(data, *args, **kwargs):
            return (None, b"") if data == b"enc_empty" else (None, b"decrypted")

        mock_win32crypt.CryptProtectData.side_effect = encrypt_side_effect
        mock_win32crypt.CryptUnprotectData.side_effect = decrypt_side_effect

        # Mock scan_clients to return an active client that is not in the database
        mock_scan.return_value = {
            "riot": {
                "connected": True,
                "pid": 9999,
                "port": "1234",
                "token": "token"
            },
            "league": {
                "connected": False
            }
        }

        mgr = AccountManager()
        
        # Mock RiotClientAPI.get_current_user to return session/userinfo info
        mgr.riot_client.is_connected = True
        mgr.riot_client.get_current_user = MagicMock(return_value={
            "preferred_username": "NewPlayer",
            "acct": {
                "game_name": "NewPlayer",
                "tag_line": "1234"
            }
        })
        # Mock LCU connection to False so we run Method 1
        mgr.lcu = MagicMock()
        mgr.lcu.is_connected = False

        # Detect active account (should auto-populate a new placeholder account)
        active_idx = mgr.detect_active_account()

        self.assertEqual(active_idx, 0)
        accounts = mgr.get_accounts()
        self.assertEqual(len(accounts), 1)
        self.assertEqual(accounts[0]["label"], "NewPlayer#1234")
        self.assertEqual(accounts[0]["tagline"], "NewPlayer#1234")
        # Password should be empty (placeholder)
        self.assertEqual(mgr.get_password(0), "")

if __name__ == "__main__":
    unittest.main()
