"""add_owner_id_to_guests

Revision ID: a1b2c3d4e5f6
Revises: d026dfaf7c4d
Create Date: 2026-02-14 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'd026dfaf7c4d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: Add nullable column
    op.add_column("guests", sa.Column("owner_id", sa.UUID(), nullable=True))

    # Step 2: Backfill — assign owner based on most recent booking's property owner
    op.execute("""
        UPDATE guests g
        SET owner_id = (
            SELECT p.owner_id
            FROM bookings b
            JOIN properties p ON b.property_id = p.id
            WHERE b.guest_id = g.id
            ORDER BY b.created_at DESC
            LIMIT 1
        )
        WHERE EXISTS (
            SELECT 1 FROM bookings b WHERE b.guest_id = g.id
        )
    """)

    # Step 3: Handle orphan guests (no bookings) — delete them
    op.execute("""
        DELETE FROM guests WHERE owner_id IS NULL
    """)

    # Step 4: Make NOT NULL
    op.alter_column("guests", "owner_id", nullable=False)

    # Step 5: Drop global unique on email (if it exists)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE guests DROP CONSTRAINT IF EXISTS guests_email_key;
        END $$;
    """)

    # Step 6: Add composite unique (email unique per owner)
    op.create_unique_constraint("uq_guests_owner_email", "guests", ["owner_id", "email"])

    # Step 7: Add FK + index
    op.create_foreign_key(
        "fk_guests_owner_id", "guests", "users",
        ["owner_id"], ["id"], ondelete="CASCADE",
    )
    op.create_index("ix_guests_owner_id", "guests", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_guests_owner_id", table_name="guests")
    op.drop_constraint("fk_guests_owner_id", "guests", type_="foreignkey")
    op.drop_constraint("uq_guests_owner_email", "guests", type_="unique")
    op.create_unique_constraint("guests_email_key", "guests", ["email"])
    op.drop_column("guests", "owner_id")
