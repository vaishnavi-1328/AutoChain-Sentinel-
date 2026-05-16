"""orders + order_event_impacts.

Revision ID: 002
Revises: 001
Create Date: 2026-05-13
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("supplier_name", sa.String, nullable=False),
        sa.Column("supplier_city", sa.String, nullable=False),
        sa.Column("supplier_country", sa.CHAR(length=2), nullable=False),
        sa.Column("supplier_lat", sa.Float, nullable=False),
        sa.Column("supplier_lng", sa.Float, nullable=False),
        sa.Column("materials", sa.String, nullable=False),
        sa.Column("quantity", sa.Numeric),
        sa.Column("quantity_unit", sa.String),
        sa.Column("expected_delivery", sa.Date, nullable=False),
        sa.Column("po_reference", sa.String),
        sa.Column("shipping_mode", sa.String, nullable=False, server_default="Sea freight"),
        sa.Column("notes", sa.String),
        sa.Column("status", sa.String, nullable=False, server_default="ON_SCHEDULE"),
        sa.Column("delay_min_days", sa.Integer, nullable=False, server_default="0"),
        sa.Column("delay_max_days", sa.Integer, nullable=False, server_default="0"),
        sa.Column("new_eta_earliest", sa.Date),
        sa.Column("new_eta_latest", sa.Date),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_orders_user_id", "orders", ["user_id"])
    op.create_index("idx_orders_status", "orders", ["status"])

    op.create_table(
        "order_event_impacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("distance_km", sa.Numeric(8, 2)),
        sa.Column("delay_contribution_days", sa.Integer),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_oei_order_id", "order_event_impacts", ["order_id"])
    op.create_index("idx_oei_event_id", "order_event_impacts", ["event_id"])


def downgrade() -> None:
    op.drop_index("idx_oei_event_id", table_name="order_event_impacts")
    op.drop_index("idx_oei_order_id", table_name="order_event_impacts")
    op.drop_table("order_event_impacts")
    op.drop_index("idx_orders_status", table_name="orders")
    op.drop_index("idx_orders_user_id", table_name="orders")
    op.drop_table("orders")
