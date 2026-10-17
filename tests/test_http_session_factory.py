"""
Unit tests for http_session_factory module.
Verifies default SSL verification behaviors and option overrides.
"""

from services.http_session_factory import create_pooled_session, get_shared_session, _shared_session
import services.http_session_factory as hsf


def test_create_pooled_session_default_ssl_verification():
    session = create_pooled_session()
    assert session.verify is True


def test_create_pooled_session_custom_ssl_verification():
    session = create_pooled_session(verify_ssl=False)
    assert session.verify is False


def test_get_shared_session_ssl_verification():
    # Reset singleton module variable if needed
    hsf._shared_session = None
    session = get_shared_session()
    assert session.verify is True
    # Singleton check
    assert get_shared_session() is session
