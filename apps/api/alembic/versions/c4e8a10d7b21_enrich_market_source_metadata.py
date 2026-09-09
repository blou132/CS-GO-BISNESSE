"""enrich market source metadata

Revision ID: c4e8a10d7b21
Revises: 9b7c6d5e4f30
Create Date: 2026-09-09
"""

import hashlib
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c4e8a10d7b21"
down_revision: str | Sequence[str] | None = "9b7c6d5e4f30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("cs2_items") as batch:
        batch.add_column(sa.Column("scm_price", sa.Numeric(precision=20, scale=8), nullable=True))
        batch.add_column(sa.Column("scm_volume", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("source_attributes", sa.JSON(), nullable=True))
    op.execute("UPDATE cs2_items SET source_attributes = '{}' WHERE source_attributes IS NULL")
    with op.batch_alter_table("cs2_items") as batch:
        batch.alter_column("source_attributes", existing_type=sa.JSON(), nullable=False)
    with op.batch_alter_table("item_stickers") as batch:
        batch.add_column(sa.Column("steam_volume", sa.Integer(), nullable=True))
    with op.batch_alter_table("platform_fee_schedules") as batch:
        batch.add_column(sa.Column("minimum_fee", sa.Numeric(precision=20, scale=8), nullable=True))
        batch.create_check_constraint(
            "ck_platform_fee_schedules_minimum_fee",
            "minimum_fee IS NULL OR minimum_fee >= 0",
        )
    with op.batch_alter_table("realized_sales") as batch:
        batch.add_column(sa.Column("fingerprint", sa.String(length=64), nullable=True))
        batch.alter_column("external_id", existing_type=sa.String(length=256), nullable=True)
    _backfill_sale_fingerprints()
    with op.batch_alter_table("realized_sales") as batch:
        batch.alter_column("fingerprint", existing_type=sa.String(length=64), nullable=False)
        batch.create_unique_constraint("uq_realized_sale_fingerprint", ["fingerprint"])


def _backfill_sale_fingerprints() -> None:
    bind = op.get_bind()
    sales = sa.table(
        "realized_sales",
        sa.column("id", sa.String),
        sa.column("mode", sa.String),
        sa.column("platform", sa.String),
        sa.column("external_id", sa.String),
        sa.column("fingerprint", sa.String),
    )
    for row in bind.execute(
        sa.select(sales.c.id, sales.c.mode, sales.c.platform, sales.c.external_id)
    ).mappings():
        value = "|".join((row.mode, row.platform, row.external_id or row.id))
        bind.execute(
            sales.update()
            .where(sales.c.id == row.id)
            .values(fingerprint=hashlib.sha256(value.encode()).hexdigest())
        )


def downgrade() -> None:
    with op.batch_alter_table("realized_sales") as batch:
        batch.drop_constraint("uq_realized_sale_fingerprint", type_="unique")
    op.execute(
        "UPDATE realized_sales SET external_id = 'derived:' || fingerprint "
        "WHERE external_id IS NULL"
    )
    with op.batch_alter_table("realized_sales") as batch:
        batch.alter_column("external_id", existing_type=sa.String(length=256), nullable=False)
        batch.drop_column("fingerprint")
    with op.batch_alter_table("platform_fee_schedules") as batch:
        batch.drop_constraint("ck_platform_fee_schedules_minimum_fee", type_="check")
        batch.drop_column("minimum_fee")
    with op.batch_alter_table("item_stickers") as batch:
        batch.drop_column("steam_volume")
    with op.batch_alter_table("cs2_items") as batch:
        batch.drop_column("source_attributes")
        batch.drop_column("scm_volume")
        batch.drop_column("scm_price")
