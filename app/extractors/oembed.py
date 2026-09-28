"""Shared oEmbed fetch helper (used by TikTok/YouTube/Pinterest/Instagram)."""

from __future__ import annotations

import json
from typing import Any

from app.core.logging import get_logger
from app.services.security.safe_http import ResponseTooLargeError, UnsafeURLError, safe_get

logger = get_logger(__name__)


async def fetch_oembed(oembed_endpoint: str) -> dict[str, Any] | None:
    try:
        response = await safe_get(
            oembed_endpoint, accept_content_types=("application/json", "text/json")
        )
    except (UnsafeURLError, ResponseTooLargeError) as exc:
        logger.info("oembed_blocked", endpoint=oembed_endpoint, error=str(exc))
        return None
    except Exception as exc:  # noqa: BLE001
        logger.info("oembed_failed", endpoint=oembed_endpoint, error=str(exc))
        return None

    if response.status_code != 200:
        return None

    try:
        return json.loads(response.content)
    except json.JSONDecodeError:
        return None
