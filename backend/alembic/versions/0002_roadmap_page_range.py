"""add roadmap page range

Revision ID: 0002_roadmap_page_range
Revises: 0001_initial
Create Date: 2026-05-20

"""
from alembic import op
import sqlalchemy as sa


revision = "0002_roadmap_page_range"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("roadmaps", sa.Column("page_start", sa.Integer()))
    op.add_column("roadmaps", sa.Column("page_end", sa.Integer()))


def downgrade() -> None:
    op.drop_column("roadmaps", "page_end")
    op.drop_column("roadmaps", "page_start")
