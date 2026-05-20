"""initial schema

Revision ID: 0001_initial
Revises: 
Create Date: 2026-05-20

"""
from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


user_role = sa.Enum("admin", "student", name="user_role")
user_status = sa.Enum("pending", "approved", "rejected", name="user_status")
attempt_status = sa.Enum("correct", "incorrect", "skipped", name="attempt_status")
roadmap_phase = sa.Enum("A", "A1", "HINT", "EXPLAIN", "RETEST", name="roadmap_phase")


def upgrade() -> None:
    user_role.create(op.get_bind(), checkfirst=True)
    user_status.create(op.get_bind(), checkfirst=True)
    attempt_status.create(op.get_bind(), checkfirst=True)
    roadmap_phase.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", user_role, nullable=False, server_default="student"),
        sa.Column("status", user_status, nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
    )

    op.create_table(
        "classes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id")),
    )

    op.create_table(
        "groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("class_id", sa.Integer(), sa.ForeignKey("classes.id")),
        sa.Column("name", sa.String(length=120), nullable=False),
    )

    op.create_table(
        "student_profiles",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("university_group", sa.String(length=10), nullable=False),
        sa.Column("class_id", sa.Integer(), sa.ForeignKey("classes.id")),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id")),
        sa.Column("avatar_url", sa.String(length=500)),
    )

    op.create_table(
        "pdfs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("uploaded_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
    )

    op.create_table(
        "pdf_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pdf_id", sa.Integer(), sa.ForeignKey("pdfs.id")),
        sa.Column("chapter", sa.String(length=120)),
        sa.Column("page_start", sa.Integer(), nullable=False),
        sa.Column("page_end", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
    )

    op.create_table(
        "roadmaps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("pdf_id", sa.Integer(), sa.ForeignKey("pdfs.id")),
        sa.Column("page_start", sa.Integer()),
        sa.Column("page_end", sa.Integer()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
    )

    op.create_table(
        "roadmap_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("roadmap_id", sa.Integer(), sa.ForeignKey("roadmaps.id")),
        sa.Column("topic", sa.String(length=255), nullable=False),
        sa.Column("question_type", sa.String(length=120), nullable=False),
        sa.Column("difficulty", sa.String(length=20), nullable=False),
        sa.Column("sequence_index", sa.Integer(), nullable=False),
        sa.Column("metadata", sa.dialects.postgresql.JSONB()),
    )

    op.create_table(
        "roadmap_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("roadmap_id", sa.Integer(), sa.ForeignKey("roadmaps.id")),
        sa.Column("target_type", sa.String(length=20), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("assigned_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
    )

    op.create_table(
        "roadmap_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("roadmap_item_id", sa.Integer(), sa.ForeignKey("roadmap_items.id")),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("status", attempt_status, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
    )

    op.create_table(
        "ai_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("roadmap_item_id", sa.Integer(), sa.ForeignKey("roadmap_items.id")),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("type_label", sa.String(length=120), nullable=False),
        sa.Column("difficulty", sa.String(length=20), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("choices", sa.dialects.postgresql.JSONB()),
        sa.Column("answer_key", sa.dialects.postgresql.JSONB()),
        sa.Column("explanation", sa.Text()),
        sa.Column("hint", sa.Text()),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="groq"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
    )

    op.create_table(
        "roadmap_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("roadmap_item_id", sa.Integer(), sa.ForeignKey("roadmap_items.id")),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("phase", roadmap_phase, nullable=False, server_default="A"),
        sa.Column("last_question_id", sa.Integer(), sa.ForeignKey("ai_questions.id")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
    )

    op.create_table(
        "practice_exams",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("uploaded_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
    )

    op.create_table(
        "practice_exam_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("practice_exam_id", sa.Integer(), sa.ForeignKey("practice_exams.id")),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
    )

    op.create_table(
        "practice_exam_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("practice_exam_id", sa.Integer(), sa.ForeignKey("practice_exams.id")),
        sa.Column("target_type", sa.String(length=20), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("assigned_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
    )

    op.create_table(
        "lesson_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("url", sa.String(length=1000), nullable=False),
        sa.Column("class_id", sa.Integer(), sa.ForeignKey("classes.id")),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id")),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
    )

    op.create_table(
        "monthly_exam_grades",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("exam_date", sa.DateTime(), nullable=False),
        sa.Column("grade", sa.Integer(), nullable=False),
        sa.Column("uploaded_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("monthly_exam_grades")
    op.drop_table("lesson_links")
    op.drop_table("practice_exam_assignments")
    op.drop_table("practice_exam_attempts")
    op.drop_table("practice_exams")
    op.drop_table("roadmap_state")
    op.drop_table("ai_questions")
    op.drop_table("roadmap_attempts")
    op.drop_table("roadmap_assignments")
    op.drop_table("roadmap_items")
    op.drop_table("roadmaps")
    op.drop_table("pdf_chunks")
    op.drop_table("pdfs")
    op.drop_table("student_profiles")
    op.drop_table("groups")
    op.drop_table("classes")
    op.drop_table("users")

    roadmap_phase.drop(op.get_bind(), checkfirst=True)
    attempt_status.drop(op.get_bind(), checkfirst=True)
    user_status.drop(op.get_bind(), checkfirst=True)
    user_role.drop(op.get_bind(), checkfirst=True)
