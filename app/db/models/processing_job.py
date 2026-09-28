from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.db.models.enums import ProcessingStatus


class ProcessingJob(Base, UUIDPKMixin, TimestampMixin):
    """Tracks async pipeline execution for a saved item (extraction -> AI -> embedding)."""

    __tablename__ = "processing_jobs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    saved_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("saved_items.id", ondelete="CASCADE"), nullable=True, index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    job_type: Mapped[str] = mapped_column(String(32), default="save_url")
    status: Mapped[str] = mapped_column(
        String(16), default=ProcessingStatus.PENDING, server_default=ProcessingStatus.PENDING
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    telegram_chat_id: Mapped[int | None] = mapped_column()
    telegram_status_message_id: Mapped[int | None] = mapped_column()
