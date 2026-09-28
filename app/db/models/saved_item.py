from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Boolean, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import get_settings
from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.db.models.enums import ProcessingStatus
from app.db.models.tag import Tag

_settings = get_settings()


class SavedItem(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "saved_items"
    __table_args__ = (
        Index("ix_saved_items_user_id_created_at", "user_id", "created_at"),
        Index("ix_saved_items_user_id_canonical_url", "user_id", "canonical_url"),
        Index(
            "ix_saved_items_search_vector",
            "search_vector",
            postgresql_using="gin",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    # --- Source ---
    url: Mapped[str] = mapped_column(Text)
    canonical_url: Mapped[str] = mapped_column(Text, index=True)
    platform: Mapped[str] = mapped_column(String(32), index=True)

    # --- Extracted content ---
    content_type: Mapped[str | None] = mapped_column(String(64), index=True)
    title: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(String(255))
    thumbnail_url: Mapped[str | None] = mapped_column(Text)
    media_type: Mapped[str | None] = mapped_column(String(32))
    transcript: Mapped[str | None] = mapped_column(Text)
    extracted_text: Mapped[str | None] = mapped_column(Text)
    extraction_method: Mapped[str | None] = mapped_column(String(32))

    # --- AI classification ---
    category: Mapped[str | None] = mapped_column(String(32), index=True)
    subcategory: Mapped[str | None] = mapped_column(String(64), index=True)
    language: Mapped[str | None] = mapped_column(String(8))
    structured_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), default=dict, server_default="{}"
    )
    item_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB().with_variant(JSON(), "sqlite"),
        default=dict,
        server_default="{}",
    )

    # --- User annotations ---
    user_note: Mapped[str | None] = mapped_column(Text)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    # --- Search ---
    searchable_text: Mapped[str | None] = mapped_column(Text)
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(_settings.embedding_dimensions), nullable=True
    )

    # --- Processing ---
    processing_status: Mapped[str] = mapped_column(
        String(16), default=ProcessingStatus.PENDING, server_default=ProcessingStatus.PENDING
    )
    processing_error: Mapped[str | None] = mapped_column(Text)

    # --- Telegram origin (for images) ---
    source_telegram_file_id: Mapped[str | None] = mapped_column(String(255))
    storage_object_key: Mapped[str | None] = mapped_column(String(512))

    last_used_at: Mapped[datetime | None] = mapped_column(nullable=True)

    tags: Mapped[list[Tag]] = relationship(secondary="saved_item_tags", viewonly=True)
