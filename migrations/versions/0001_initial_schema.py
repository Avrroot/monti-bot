"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-27
"""
from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = 1536


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                   server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_username", sa.String(255), nullable=True),
        sa.Column("first_name", sa.String(255), nullable=True),
        sa.Column("locale", sa.String(8), server_default="ru", nullable=False),
        sa.Column("is_blocked", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
    )
    op.create_index("ix_users_telegram_user_id", "users", ["telegram_user_id"], unique=True)

    op.create_table(
        "user_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                   server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("locale", sa.String(8), server_default="ru", nullable=False),
        sa.Column("notifications_enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_user_settings_user_id_users",
                                 ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_user_settings"),
        sa.UniqueConstraint("user_id", name="uq_user_settings_user_id"),
    )

    op.create_table(
        "saved_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                   server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("content_type", sa.String(64), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("author", sa.String(255), nullable=True),
        sa.Column("thumbnail_url", sa.Text(), nullable=True),
        sa.Column("media_type", sa.String(32), nullable=True),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("extraction_method", sa.String(32), nullable=True),
        sa.Column("category", sa.String(32), nullable=True),
        sa.Column("subcategory", sa.String(64), nullable=True),
        sa.Column("language", sa.String(8), nullable=True),
        sa.Column("structured_data", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("user_note", sa.Text(), nullable=True),
        sa.Column("is_favorite", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("searchable_text", sa.Text(), nullable=True),
        sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(EMBEDDING_DIM), nullable=True),
        sa.Column("processing_status", sa.String(16), server_default="pending", nullable=False),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column("source_telegram_file_id", sa.String(255), nullable=True),
        sa.Column("storage_object_key", sa.String(512), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_saved_items_user_id_users",
                                 ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_saved_items"),
    )
    op.create_index("ix_saved_items_user_id", "saved_items", ["user_id"])
    op.create_index("ix_saved_items_user_id_created_at", "saved_items", ["user_id", "created_at"])
    op.create_index(
        "ix_saved_items_user_id_canonical_url", "saved_items", ["user_id", "canonical_url"]
    )
    op.create_index("ix_saved_items_canonical_url", "saved_items", ["canonical_url"])
    op.create_index("ix_saved_items_platform", "saved_items", ["platform"])
    op.create_index("ix_saved_items_content_type", "saved_items", ["content_type"])
    op.create_index("ix_saved_items_category", "saved_items", ["category"])
    op.create_index("ix_saved_items_subcategory", "saved_items", ["subcategory"])
    op.create_index(
        "ix_saved_items_search_vector", "saved_items", ["search_vector"], postgresql_using="gin"
    )
    op.execute(
        "CREATE INDEX ix_saved_items_embedding_hnsw ON saved_items "
        "USING hnsw (embedding vector_cosine_ops)"
    )

    op.execute(
        """
        CREATE FUNCTION saved_items_search_vector_update() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector := to_tsvector('simple', coalesce(NEW.searchable_text, ''));
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_saved_items_search_vector
        BEFORE INSERT OR UPDATE OF searchable_text ON saved_items
        FOR EACH ROW EXECUTE FUNCTION saved_items_search_vector_update();
        """
    )

    op.create_table(
        "tags",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                   server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_tags_user_id_users",
                                 ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_tags"),
        sa.UniqueConstraint("user_id", "name", name="uq_tags_user_id_name"),
    )
    op.create_index("ix_tags_user_id", "tags", ["user_id"])
    op.create_index("ix_tags_name", "tags", ["name"])

    op.create_table(
        "saved_item_tags",
        sa.Column("saved_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tag_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["saved_item_id"], ["saved_items.id"],
                                 name="fk_saved_item_tags_saved_item_id_saved_items",
                                 ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"],
                                 name="fk_saved_item_tags_tag_id_tags", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("saved_item_id", "tag_id", name="pk_saved_item_tags"),
    )

    op.create_table(
        "collections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                   server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_collections_user_id_users",
                                 ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_collections"),
        sa.UniqueConstraint("user_id", "name", name="uq_collections_user_id_name"),
    )
    op.create_index("ix_collections_user_id", "collections", ["user_id"])

    op.create_table(
        "collection_items",
        sa.Column("collection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("saved_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["collection_id"], ["collections.id"],
                                 name="fk_collection_items_collection_id_collections",
                                 ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["saved_item_id"], ["saved_items.id"],
                                 name="fk_collection_items_saved_item_id_saved_items",
                                 ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("collection_id", "saved_item_id", name="pk_collection_items"),
    )

    op.create_table(
        "processing_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                   server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("saved_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("job_type", sa.String(32), server_default="save_url", nullable=False),
        sa.Column("status", sa.String(16), server_default="pending", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=True),
        sa.Column("telegram_status_message_id", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_processing_jobs_user_id_users",
                                 ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["saved_item_id"], ["saved_items.id"],
                                 name="fk_processing_jobs_saved_item_id_saved_items",
                                 ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_processing_jobs"),
        sa.UniqueConstraint("idempotency_key", name="uq_processing_jobs_idempotency_key"),
    )
    op.create_index("ix_processing_jobs_user_id", "processing_jobs", ["user_id"])
    op.create_index("ix_processing_jobs_saved_item_id", "processing_jobs", ["saved_item_id"])
    op.create_index(
        "ix_processing_jobs_idempotency_key", "processing_jobs", ["idempotency_key"], unique=True
    )

    op.create_table(
        "usage_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                   server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_usage_events_user_id_users",
                                 ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_usage_events"),
    )
    op.create_index("ix_usage_events_user_id", "usage_events", ["user_id"])
    op.create_index("ix_usage_events_event_type", "usage_events", ["event_type"])


def downgrade() -> None:
    op.drop_table("usage_events")
    op.drop_table("processing_jobs")
    op.drop_table("collection_items")
    op.drop_table("collections")
    op.drop_table("saved_item_tags")
    op.drop_table("tags")
    op.execute("DROP TRIGGER IF EXISTS trg_saved_items_search_vector ON saved_items")
    op.execute("DROP FUNCTION IF EXISTS saved_items_search_vector_update")
    op.drop_table("saved_items")
    op.drop_table("user_settings")
    op.drop_table("users")
