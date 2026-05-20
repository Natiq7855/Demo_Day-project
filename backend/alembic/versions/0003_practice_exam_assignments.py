"""add practice exam assignments

Revision ID: 0003_practice_exam_assignments
Revises: 0002_roadmap_page_range
Create Date: 2026-05-20

"""
from alembic import op
import sqlalchemy as sa


revision = "0003_practice_exam_assignments"
down_revision = "0002_roadmap_page_range"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "practice_exam_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("practice_exam_id", sa.Integer(), sa.ForeignKey("practice_exams.id")),
        sa.Column("target_type", sa.String(length=20), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("assigned_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("practice_exam_assignments")
