from __future__ import annotations

from app.core.config import get_settings
from app.services.storage.base import ObjectStorageProtocol


def get_object_storage() -> ObjectStorageProtocol:
    settings = get_settings()
    if settings.storage_backend == "local":
        from app.services.storage.local_storage import LocalObjectStorage

        return LocalObjectStorage()
    if settings.storage_backend == "s3":
        from app.services.storage.object_storage import ObjectStorage

        return ObjectStorage()
    raise ValueError(f"Unsupported STORAGE_BACKEND: {settings.storage_backend}")
