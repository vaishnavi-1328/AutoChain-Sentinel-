"""initial schema: users, user_profiles, events, user_event_impacts.

Revision ID: 001
Revises:
Create Date: 2026-05-12
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String, unique=True, nullable=False),
        sa.Column("password_hash", sa.String, nullable=False),
        sa.Column("company", sa.String),
        sa.Column("role", sa.String),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "user_profiles",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("watched_regions", postgresql.ARRAY(sa.String), server_default="{}"),
        sa.Column("product_categories", postgresql.ARRAY(sa.String), server_default="{}"),
        sa.Column("sku_codes", postgresql.ARRAY(sa.String), server_default="{}"),
        sa.Column("supplier_names", postgresql.ARRAY(sa.String), server_default="{}"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("type", sa.String, nullable=False),
        sa.Column("severity", sa.String, nullable=False),
        sa.Column("title", sa.String, nullable=False),
        sa.Column("summary", sa.String),
        sa.Column("source_url", sa.String),
        sa.Column("source_name", sa.String),
        sa.Column("lat", sa.Float),
        sa.Column("lng", sa.Float),
        sa.Column("location_name", sa.String),
        sa.Column("country_code", sa.CHAR(length=2)),
        sa.Column("delay_min_days", sa.Integer),
        sa.Column("delay_max_days", sa.Integer),
        sa.Column("delay_confidence", sa.Numeric(4, 3)),
        sa.Column("neo4j_node_id", sa.String),
        sa.Column("affected_route_count", sa.Integer),
        sa.Column("timestamp_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_events_timestamp", "events", [sa.text("timestamp_utc DESC")])
    op.create_index("idx_events_country", "events", ["country_code"])
    op.create_index("idx_events_severity", "events", ["severity"])

    op.create_table(
        "user_event_impacts",
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("events.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("affected_sku_count", sa.Integer, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("user_event_impacts")
    op.drop_index("idx_events_severity", table_name="events")
    op.drop_index("idx_events_country", table_name="events")
    op.drop_index("idx_events_timestamp", table_name="events")
    op.drop_table("events")
    op.drop_table("user_profiles")
    op.drop_table("users")
