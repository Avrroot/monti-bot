from __future__ import annotations

import pytest
from app.services.security.safe_http import (
    UnsafeURLError,
    _is_ip_blocked,
    validate_url_safety,
)


@pytest.mark.parametrize(
    ("ip", "blocked"),
    [
        ("127.0.0.1", True),
        ("localhost", True),  # not a valid IP -> ValueError path -> blocked
        ("10.0.0.5", True),
        ("172.16.0.5", True),
        ("192.168.1.5", True),
        ("169.254.169.254", True),  # cloud metadata endpoint
        ("::1", True),
        ("8.8.8.8", False),
        ("1.1.1.1", False),
    ],
)
def test_is_ip_blocked(ip: str, blocked: bool) -> None:
    assert _is_ip_blocked(ip) is blocked


def test_validate_url_safety_rejects_disallowed_scheme() -> None:
    with pytest.raises(UnsafeURLError):
        validate_url_safety("file:///etc/passwd")


def test_validate_url_safety_rejects_ftp_scheme() -> None:
    with pytest.raises(UnsafeURLError):
        validate_url_safety("ftp://example.com/file")


def test_validate_url_safety_rejects_localhost() -> None:
    with pytest.raises(UnsafeURLError):
        validate_url_safety("http://localhost/admin")


def test_validate_url_safety_rejects_loopback_ip_directly() -> None:
    with pytest.raises(UnsafeURLError):
        validate_url_safety("http://127.0.0.1/admin")


def test_validate_url_safety_rejects_private_ip_directly() -> None:
    with pytest.raises(UnsafeURLError):
        validate_url_safety("http://192.168.1.1/admin")


def test_validate_url_safety_allows_public_https() -> None:
    # example.com resolves publicly; should not raise.
    validate_url_safety("https://example.com/path")


@pytest.fixture
def with_proxy(monkeypatch: pytest.MonkeyPatch):
    from app.core.config import get_settings

    monkeypatch.setenv("PROXY_URL", "socks5://127.0.0.1:1080")
    get_settings.cache_clear()
    yield
    monkeypatch.delenv("PROXY_URL", raising=False)
    get_settings.cache_clear()


def test_validate_url_safety_with_proxy_skips_local_dns(with_proxy) -> None:
    # This hostname cannot resolve locally at all -- with a proxy configured
    # we must not try (the proxy resolves it remotely instead).
    validate_url_safety("https://this-domain-does-not-exist-xyz123.invalid/path")


def test_validate_url_safety_with_proxy_still_blocks_literal_loopback_ip(with_proxy) -> None:
    with pytest.raises(UnsafeURLError):
        validate_url_safety("http://127.0.0.1/admin")


def test_validate_url_safety_with_proxy_still_blocks_literal_private_ip(with_proxy) -> None:
    with pytest.raises(UnsafeURLError):
        validate_url_safety("http://169.254.169.254/latest/meta-data/")


def test_validate_url_safety_with_proxy_still_blocks_localhost_hostname(with_proxy) -> None:
    with pytest.raises(UnsafeURLError):
        validate_url_safety("http://localhost/admin")
