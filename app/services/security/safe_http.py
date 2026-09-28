"""SSRF-hardened HTTP client used by every content extractor and the image
download path.

Threat model addressed:
- scheme allowlist (http/https only)
- DNS resolution is checked before connecting; loopback/private/link-local/
  reserved/multicast IPs are rejected (blocks localhost, 169.254.169.254
  metadata endpoints, RFC1918 ranges, etc.)
- each redirect hop is re-validated against the same rules (no bouncing
  through a public host that then 302s to an internal one)
- response size is capped while streaming, not after the fact
- a request timeout is always enforced
- optional Content-Type allowlist for callers that only want HTML/JSON/images

When PROXY_URL is set (deployments where the host has no direct route to
Telegram/OpenAI/social platforms and everything goes through an outbound
SOCKS5 tunnel), local DNS resolution is unreliable or simply unavailable --
that's the whole reason the proxy exists. In that mode we skip the local
`getaddrinfo`-based check (the real connection is made by the proxy, on a
different network, and the SOCKS5 proxy always resolves DNS itself rather
than us) and only block obviously-dangerous *literal* IP targets in the
URL itself. See
`validate_url_safety` for the exact split.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_ALLOWED_SCHEMES = {"http", "https"}

_SAFE_USER_AGENT = "SaveBot/1.0 (+https://savebot.example; content preview fetcher)"


class UnsafeURLError(Exception):
    """Raised when a URL fails SSRF/security validation."""


class ResponseTooLargeError(Exception):
    pass


@dataclass(slots=True)
class SafeResponse:
    status_code: int
    headers: httpx.Headers
    content: bytes
    final_url: str


def _is_ip_blocked(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def validate_host_resolves_safely(host: str) -> None:
    """Resolve `host` and raise UnsafeURLError if any resolved IP is unsafe."""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise UnsafeURLError(f"DNS resolution failed for host: {host}") from exc

    if not infos:
        raise UnsafeURLError(f"DNS resolution returned no addresses for host: {host}")

    for info in infos:
        ip_str = str(info[4][0])
        if _is_ip_blocked(ip_str):
            raise UnsafeURLError(f"Host {host} resolves to a disallowed IP: {ip_str}")


def _is_literal_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


_LITERAL_BLOCKED_HOSTNAMES = {"localhost", "localhost.localdomain", "ip6-localhost"}


def validate_url_safety(url: str) -> httpx.URL:
    parsed = httpx.URL(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise UnsafeURLError(f"Disallowed URL scheme: {parsed.scheme}")
    if not parsed.host:
        raise UnsafeURLError("URL has no host")

    if get_settings().proxy_url:
        # Can't reliably resolve DNS locally in this mode -- the proxy does
        # it remotely. Still reject requests that spell out a dangerous
        # target directly by literal IP or well-known local hostname (a real
        # SSRF vector against the proxy's own network too), but let other
        # hostnames pass through to the proxy to resolve.
        host_lower = parsed.host.lower()
        if host_lower in _LITERAL_BLOCKED_HOSTNAMES:
            raise UnsafeURLError(f"Disallowed literal hostname target: {parsed.host}")
        if _is_literal_ip(parsed.host) and _is_ip_blocked(parsed.host):
            raise UnsafeURLError(f"Disallowed literal IP target: {parsed.host}")
        return parsed

    validate_host_resolves_safely(parsed.host)
    return parsed


async def safe_get(
    url: str,
    *,
    max_redirects: int | None = None,
    max_bytes: int | None = None,
    timeout_seconds: float | None = None,
    accept_content_types: tuple[str, ...] | None = None,
) -> SafeResponse:
    """Fetch a URL with SSRF protections and a hard response-size cap.

    Redirects are followed manually (not via httpx's follow_redirects) so
    every hop can be re-validated.
    """
    settings = get_settings()
    max_redirects = max_redirects if max_redirects is not None else settings.http_max_redirects
    max_bytes = max_bytes if max_bytes is not None else settings.http_max_response_bytes
    timeout_seconds = (
        timeout_seconds if timeout_seconds is not None else settings.http_timeout_seconds
    )

    current_url = url
    async with httpx.AsyncClient(
        follow_redirects=False,
        timeout=timeout_seconds,
        headers={"User-Agent": _SAFE_USER_AGENT},
        proxy=settings.proxy_url,
    ) as client:
        for hop in range(max_redirects + 1):
            validate_url_safety(current_url)

            async with client.stream("GET", current_url) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location or hop == max_redirects:
                        raise UnsafeURLError("Too many redirects or missing Location header")
                    current_url = str(response.url.join(location))
                    continue

                content_type = response.headers.get("content-type", "")
                if accept_content_types and not any(
                    content_type.startswith(ct) for ct in accept_content_types
                ):
                    raise UnsafeURLError(f"Disallowed content-type: {content_type}")

                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > max_bytes:
                    raise ResponseTooLargeError(
                        f"Content-Length {content_length} exceeds limit {max_bytes}"
                    )

                chunks = bytearray()
                async for chunk in response.aiter_bytes():
                    chunks.extend(chunk)
                    if len(chunks) > max_bytes:
                        raise ResponseTooLargeError(
                            f"Response exceeded max size of {max_bytes} bytes"
                        )

                return SafeResponse(
                    status_code=response.status_code,
                    headers=response.headers,
                    content=bytes(chunks),
                    final_url=str(response.url),
                )

    raise UnsafeURLError("Redirect loop exceeded max_redirects without resolving")
