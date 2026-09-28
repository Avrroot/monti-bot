"""URL normalization and platform detection.

These are pure functions with no I/O so they can be unit tested without any
network or database dependency.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from app.db.models.enums import Platform

# Tracking / analytics query params stripped during normalization so that the
# same content reached via different campaigns dedupes to one saved item.
_TRACKING_PARAM_PATTERNS = (
    re.compile(r"^utm_.*$"),
    re.compile(r"^fbclid$"),
    re.compile(r"^gclid$"),
    re.compile(r"^gclsrc$"),
    re.compile(r"^dclid$"),
    re.compile(r"^msclkid$"),
    re.compile(r"^mc_(eid|cid)$"),
    re.compile(r"^igshid$"),
    re.compile(r"^igsh$"),
    re.compile(r"^si$"),  # youtube/spotify share id
    re.compile(r"^ref_?.*$"),
    re.compile(r"^spm$"),
    re.compile(r"^_ga$"),
    re.compile(r"^yclid$"),
)

_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)


def _is_tracking_param(key: str) -> bool:
    key_lower = key.lower()
    return any(p.match(key_lower) for p in _TRACKING_PARAM_PATTERNS)


def normalize_url(raw_url: str) -> str:
    """Produce a canonical form of a URL for dedup and safe fetching.

    - lowercases scheme/host
    - strips default ports
    - drops tracking query params
    - sorts remaining query params for stable comparison
    - drops the fragment
    - strips a single trailing slash from the path (except root)
    """
    url = raw_url.strip()
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", url):
        url = f"https://{url}"

    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    if netloc.startswith("www."):
        netloc = netloc[4:]

    if ":" in netloc:
        host, _, port = netloc.partition(":")
        default_port = {"http": "80", "https": "443"}.get(scheme)
        if port == default_port:
            netloc = host

    path = parsed.path or ""
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")

    query_pairs = [
        (k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if not _is_tracking_param(k)
    ]
    query_pairs.sort()
    query = urlencode(query_pairs)

    canonical = urlunparse((scheme, netloc, path, "", query, ""))
    return canonical


def extract_first_url(text: str) -> str | None:
    match = _URL_RE.search(text)
    return match.group(0) if match else None


def looks_like_url(text: str) -> bool:
    stripped = text.strip()
    if not stripped or " " in stripped or "\n" in stripped:
        return bool(_URL_RE.fullmatch(stripped)) if stripped else False
    if _URL_RE.match(stripped):
        return True
    # bare domains without scheme, e.g. "example.com/path"
    bare_domain = re.match(
        r"^[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+)+(/[^\s]*)?$", stripped
    )
    return bool(bare_domain)


_PLATFORM_HOST_MAP: tuple[tuple[re.Pattern[str], Platform], ...] = (
    (re.compile(r"(^|\.)instagram\.com$"), Platform.INSTAGRAM),
    (re.compile(r"(^|\.)instagr\.am$"), Platform.INSTAGRAM),
    (re.compile(r"(^|\.)tiktok\.com$"), Platform.TIKTOK),
    (re.compile(r"(^|\.)pinterest\.[a-z.]+$"), Platform.PINTEREST),
    (re.compile(r"(^|\.)pin\.it$"), Platform.PINTEREST),
    (re.compile(r"(^|\.)threads\.net$"), Platform.THREADS),
    (re.compile(r"(^|\.)threads\.com$"), Platform.THREADS),
)


def detect_platform(url: str) -> Platform:
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]

    if re.search(r"(^|\.)youtube\.com$", host) or re.search(r"(^|\.)youtu\.be$", host):
        if "/shorts/" in urlparse(url).path:
            return Platform.YOUTUBE_SHORTS
        return Platform.YOUTUBE

    for pattern, platform in _PLATFORM_HOST_MAP:
        if pattern.search(host):
            return platform

    return Platform.WEB
