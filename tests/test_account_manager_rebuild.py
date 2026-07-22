import unittest
import os
from unittest.mock import MagicMock

from services.account_manager import AccountManager


class TestAccountManagerRebuild(unittest.TestCase):

    def setUp(self):
        self.mgr = AccountManager()

    def test_encrypt_decrypt_fallback(self):
        secret = "MySuperSecretPassword123!"
        encrypted = self.mgr._encrypt(secret)
        self.assertTrue(len(encrypted) > 0)

        decrypted = self.mgr._decrypt(encrypted)
        self.assertEqual(decrypted, secret)

    def test_account_crud_lifecycle(self):
        initial_count = len(self.mgr.get_all_accounts())

        # Add account
        idx = self.mgr.add_account("Smurf Account", "TestUser", "Pass123", region="NA1")
        self.assertGreaterEqual(idx, 0)
        self.assertEqual(len(self.mgr.get_all_accounts()), initial_count + 1)

        # Get account decrypted
        acct = self.mgr.get_account(idx, decrypt_password=True)
        self.assertEqual(acct["username"], "TestUser")
        self.assertEqual(acct["password"], "Pass123")
        self.assertEqual(acct["label"], "Smurf Account")

        # Delete account
        success = self.mgr.delete_account(idx)
        self.assertTrue(success)
        self.assertEqual(len(self.mgr.get_all_accounts()), initial_count)


if __name__ == "__main__":
    unittest.main()
