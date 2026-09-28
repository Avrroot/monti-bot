"""Storage backend abstraction -- see local_storage.py for why this exists."""

from __future__ import annotations

from typing import Protocol


class ObjectStorageProtocol(Protocol):
    async def ensure_bucket(self) -> None: ...

    async def upload_bytes(
        self, data: bytes, *, content_type: str, key_prefix: str = "images"
    ) -> str: ...

    async def delete(self, key: str) -> None: ...

    async def delete_many(self, keys: list[str]) -> None: ...

    async def get_bytes(self, key: str) -> bytes: ...
