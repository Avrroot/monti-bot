"""S3-compatible object storage client (works against MinIO or real S3)."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

import aioboto3

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class ObjectStorage:
    def __init__(self) -> None:
        settings = get_settings()
        self._bucket = settings.s3_bucket
        self._session = aioboto3.Session()
        self._kwargs = {
            "endpoint_url": settings.s3_endpoint,
            "aws_access_key_id": settings.s3_access_key,
            "aws_secret_access_key": settings.s3_secret_key,
            "region_name": settings.s3_region,
        }

    @asynccontextmanager
    async def _client(self):
        async with self._session.client("s3", **self._kwargs) as client:
            yield client

    async def ensure_bucket(self) -> None:
        async with self._client() as client:
            try:
                await client.head_bucket(Bucket=self._bucket)
            except Exception:  # noqa: BLE001
                await client.create_bucket(Bucket=self._bucket)

    async def upload_bytes(
        self, data: bytes, *, content_type: str, key_prefix: str = "images"
    ) -> str:
        key = f"{key_prefix}/{uuid.uuid4().hex}"
        async with self._client() as client:
            await client.put_object(
                Bucket=self._bucket, Key=key, Body=data, ContentType=content_type
            )
        return key

    async def delete(self, key: str) -> None:
        async with self._client() as client:
            await client.delete_object(Bucket=self._bucket, Key=key)

    async def delete_many(self, keys: list[str]) -> None:
        if not keys:
            return
        async with self._client() as client:
            await client.delete_objects(
                Bucket=self._bucket, Delete={"Objects": [{"Key": k} for k in keys]}
            )

    async def get_bytes(self, key: str) -> bytes:
        async with self._client() as client:
            response = await client.get_object(Bucket=self._bucket, Key=key)
            return await response["Body"].read()
