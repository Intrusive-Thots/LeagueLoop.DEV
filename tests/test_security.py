import unittest
from services.security import CredentialSanitizer


class TestCredentialSanitizer(unittest.TestCase):

    def test_sanitize_text_redacts_auth_token(self):
        raw = "Connecting with auth_token=secret12345 to LCU"
        sanitized = CredentialSanitizer.sanitize_text(raw)
        self.assertNotIn("secret12345", sanitized)
        self.assertIn("[REDACTED]", sanitized)

    def test_sanitize_dict_redacts_sensitive_keys(self):
        raw_data = {
            "user": "summoner1",
            "auth_token": "super_secret_token",
            "nested": {
                "password": "my_password_123"
            }
        }
        clean_data = CredentialSanitizer.sanitize_dict(raw_data)
        self.assertEqual(clean_data["auth_token"], "[REDACTED]")
        self.assertEqual(clean_data["nested"]["password"], "[REDACTED]")
        self.assertEqual(clean_data["user"], "summoner1")


if __name__ == "__main__":
    unittest.main()
