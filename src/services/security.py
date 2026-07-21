"""
Security & Credential Protection Module
Sanitizes sensitive Riot LCU authentication tokens and passwords from log strings and crash dumps.
"""
import re
from typing import Any, Dict


class CredentialSanitizer:
    """Scrubs sensitive API tokens, passwords, and basic auth headers."""

    # Regex patterns for matching auth tokens and basic auth headers
    TOKEN_PATTERNS = [
        r'(?i)(remotecfg-auth-token|auth-token|token|password|auth_token)=([^\s&"\']+)',
        r'(?i)"(auth_token|token|password|auth|authorization)"\s*:\s*"(.*?)"',
        r'Basic\s+[A-Za-z0-9+/=]+',
    ]

    @classmethod
    def sanitize_text(cls, text: str) -> str:
        """Sanitizes text by replacing sensitive credentials with REDACTED."""
        if not text or not isinstance(text, str):
            return text

        sanitized = text
        for pattern in cls.TOKEN_PATTERNS:
            def _replace(match):
                if match.group(0).startswith("Basic "):
                    return "Basic [REDACTED]"
                if len(match.groups()) >= 2:
                    return f'{match.group(1)}="[REDACTED]"'
                return match.group(0)

            sanitized = re.sub(pattern, _replace, sanitized)

        return sanitized

    @classmethod
    def sanitize_dict(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively scrubs dictionary values containing sensitive keys."""
        if not isinstance(data, dict):
            return data

        clean_dict = {}
        sensitive_keys = {"token", "auth_token", "password", "authorization", "secret"}

        for k, v in data.items():
            if str(k).lower() in sensitive_keys:
                clean_dict[k] = "[REDACTED]"
            elif isinstance(v, dict):
                clean_dict[k] = cls.sanitize_dict(v)
            elif isinstance(v, str):
                clean_dict[k] = cls.sanitize_text(v)
            else:
                clean_dict[k] = v

        return clean_dict
