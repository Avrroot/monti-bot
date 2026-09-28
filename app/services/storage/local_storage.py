"""Local-filesystem object storage -- the default backend.

Same async interface as `ObjectStorage` (S3/MinIO), so callers don't care
which one they get (see `factory.py`). Exists because requiring a
third-party pre-built image (MinIO, and its alternatives) turned out to be a
real deployment liability: several previously-public registries started
gating anonymous pulls behind login during 2024-2025. For a single-VPS
personal/family deployment, a shared Docker volume is simpler and has zero
registry dependency. Use `STORAGE_BACKEND=s3` (see `object_storage.py`) if
you actually need S3 semantics -- e.g. spreading bot/worker across multiple
hosts that don't share a filesystem.
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class LocalObjectStorage:
    def __init__(self) -> None:
        settings = get_settings()
        self._root = Path(settings.local_storage_path)

    def _path_for(self, key: str) -> Path:
        # `key` is always produced by upload_bytes below (uuid hex, no path
        # separators), but guard against path traversal from any other caller.
        path = (self._root / key).resolve()
        if self._root.resolve() not in path.parents and path != self._root.resolve():
            raise ValueError(f"Invalid storage key: {key}")
        return path

    async def ensure_bucket(self) -> None:
        await asyncio.to_thread(self._root.mkdir, parents=True, exist_ok=True)

    async def upload_bytes(
        self, data: bytes, *, content_type: str, key_prefix: str = "images"
    ) -> str:
        key = f"{key_prefix}/{uuid.uuid4().hex}"
        path = self._path_for(key)

        def _write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

        await asyncio.to_thread(_write)
        return key

    async def delete(self, key: str) -> None:
        path = self._path_for(key)
        await asyncio.to_thread(path.unlink, missing_ok=True)

    async def delete_many(self, keys: list[str]) -> None:
        for key in keys:
            await self.delete(key)

    async def get_bytes(self, key: str) -> bytes:
        path = self._path_for(key)
        return await asyncio.to_thread(path.read_bytes)
