from __future__ import annotations

import pytest
from app.db.models.enums import Platform
from app.services.content.url_utils import (
    detect_platform,
    extract_first_url,
    looks_like_url,
    normalize_url,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://Example.com/Path/", "https://example.com/Path"),
        ("http://www.example.com/path", "http://example.com/path"),
        ("https://example.com:443/path", "https://example.com/path"),
        ("http://example.com:80/path", "http://example.com/path"),
        ("https://example.com/path#fragment", "https://example.com/path"),
        ("example.com/path", "https://example.com/path"),
    ],
)
def test_normalize_url_basic(raw: str, expected: str) -> None:
    assert normalize_url(raw) == expected


def test_normalize_url_strips_tracking_params() -> None:
    raw = "https://example.com/p?utm_source=ig&utm_medium=social&fbclid=abc123&id=42"
    normalized = normalize_url(raw)
    assert "utm_source" not in normalized
    assert "fbclid" not in normalized
    assert "id=42" in normalized


def test_normalize_url_sorts_query_params_for_stable_dedup() -> None:
    a = normalize_url("https://example.com/p?b=2&a=1")
    b = normalize_url("https://example.com/p?a=1&b=2")
    assert a == b


def test_normalize_url_dedupes_same_content_different_campaigns() -> None:
    a = normalize_url("https://example.com/reel/1?utm_source=instagram")
    b = normalize_url("https://example.com/reel/1?utm_source=tiktok")
    assert a == b


@pytest.mark.parametrize(
    ("url", "expected_platform"),
    [
        ("https://www.instagram.com/reel/abc123/", Platform.INSTAGRAM),
        ("https://instagr.am/p/abc123/", Platform.INSTAGRAM),
        ("https://www.tiktok.com/@user/video/12345", Platform.TIKTOK),
        ("https://www.youtube.com/watch?v=abc123", Platform.YOUTUBE),
        ("https://youtu.be/abc123", Platform.YOUTUBE),
        ("https://www.youtube.com/shorts/abc123", Platform.YOUTUBE_SHORTS),
        ("https://www.pinterest.com/pin/12345/", Platform.PINTEREST),
        ("https://pin.it/abc123", Platform.PINTEREST),
        ("https://www.threads.net/@user/post/abc123", Platform.THREADS),
        ("https://www.example.com/some-article", Platform.WEB),
    ],
)
def test_detect_platform(url: str, expected_platform: Platform) -> None:
    assert detect_platform(url) == expected_platform


def test_extract_first_url_from_surrounding_text() -> None:
    text = "check this out https://example.com/x?a=1 pretty cool right"
    assert extract_first_url(text) == "https://example.com/x?a=1"


def test_extract_first_url_returns_none_when_absent() -> None:
    assert extract_first_url("найди ресторан на крыше") is None


def test_looks_like_url_true_for_bare_url() -> None:
    assert looks_like_url("https://example.com/path")


def test_looks_like_url_false_for_search_query() -> None:
    assert not looks_like_url("найди тот ресторан в Париже")
