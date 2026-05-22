import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


json_type = JSON().with_variant(JSONB, "postgresql")


class UserRole(str, enum.Enum):
    admin = "admin"
    student = "student"


class UserStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class AttemptStatus(str, enum.Enum):
    correct = "correct"
    incorrect = "incorrect"
    skipped = "skipped"


class RoadmapPhase(str, enum.Enum):
    A = "A"
    A1 = "A1"
    HINT = "HINT"
    EXPLAIN = "EXPLAIN"
    RETEST = "RETEST"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.student)
    status: Mapped[UserStatus] = mapped_column(Enum(UserStatus), default=UserStatus.pending)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    student_profile: Mapped["StudentProfile"] = relationship(back_populates="user", uselist=False)


class Class(Base):
    __tablename__ = "classes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"))
    name: Mapped[str] = mapped_column(String(120))


class StudentProfile(Base):
    __tablename__ = "student_profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255))
    university_group: Mapped[str] = mapped_column(String(10))
    class_id: Mapped[int | None] = mapped_column(ForeignKey("classes.id"))
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id"))
    avatar_url: Mapped[str | None] = mapped_column(String(500))

    user: Mapped[User] = relationship(back_populates="student_profile")


class Pdf(Base):
    __tablename__ = "pdfs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(500))
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PdfChunk(Base):
    __tablename__ = "pdf_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pdf_id: Mapped[int] = mapped_column(ForeignKey("pdfs.id"))
    chapter: Mapped[str | None] = mapped_column(String(120))
    page_start: Mapped[int] = mapped_column(Integer)
    page_end: Mapped[int] = mapped_column(Integer)
    chunk_index: Mapped[int] = mapped_column(Integer)
    content_text: Mapped[str] = mapped_column(Text)


class Roadmap(Base):
    __tablename__ = "roadmaps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    pdf_id: Mapped[int] = mapped_column(ForeignKey("pdfs.id"))
    page_start: Mapped[int | None] = mapped_column(Integer)
    page_end: Mapped[int | None] = mapped_column(Integer)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RoadmapItem(Base):
    __tablename__ = "roadmap_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    roadmap_id: Mapped[int] = mapped_column(ForeignKey("roadmaps.id"))
    topic: Mapped[str] = mapped_column(String(255))
    question_type: Mapped[str] = mapped_column(String(120))
    difficulty: Mapped[str] = mapped_column(String(20))
    sequence_index: Mapped[int] = mapped_column(Integer)
    metadata_: Mapped[dict | None] = mapped_column("metadata", json_type)


class RoadmapAssignment(Base):
    __tablename__ = "roadmap_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    roadmap_id: Mapped[int] = mapped_column(ForeignKey("roadmaps.id"))
    target_type: Mapped[str] = mapped_column(String(20))
    target_id: Mapped[int] = mapped_column(Integer)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RoadmapAttempt(Base):
    __tablename__ = "roadmap_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    roadmap_item_id: Mapped[int] = mapped_column(ForeignKey("roadmap_items.id"))
    attempt_no: Mapped[int] = mapped_column(Integer)
    status: Mapped[AttemptStatus] = mapped_column(Enum(AttemptStatus))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RoadmapState(Base):
    __tablename__ = "roadmap_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    roadmap_item_id: Mapped[int] = mapped_column(ForeignKey("roadmap_items.id"))
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    phase: Mapped[RoadmapPhase] = mapped_column(Enum(RoadmapPhase), default=RoadmapPhase.A)
    last_question_id: Mapped[int | None] = mapped_column(ForeignKey("ai_questions.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AiQuestion(Base):
    __tablename__ = "ai_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    roadmap_item_id: Mapped[int] = mapped_column(ForeignKey("roadmap_items.id"))
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    type_label: Mapped[str] = mapped_column(String(120))
    difficulty: Mapped[str] = mapped_column(String(20))
    question_text: Mapped[str] = mapped_column(Text)
    choices: Mapped[dict | None] = mapped_column(json_type)
    answer_key: Mapped[dict | None] = mapped_column(json_type)
    explanation: Mapped[str | None] = mapped_column(Text)
    hint: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(20), default="gemini")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PracticeExam(Base):
    __tablename__ = "practice_exams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(500))
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PracticeExamAttempt(Base):
    __tablename__ = "practice_exam_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    practice_exam_id: Mapped[int] = mapped_column(ForeignKey("practice_exams.id"))
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    score: Mapped[int] = mapped_column(Integer)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PracticeExamAssignment(Base):
    __tablename__ = "practice_exam_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    practice_exam_id: Mapped[int] = mapped_column(ForeignKey("practice_exams.id"))
    target_type: Mapped[str] = mapped_column(String(20))
    target_id: Mapped[int] = mapped_column(Integer)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class LessonLink(Base):
    __tablename__ = "lesson_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(1000))
    class_id: Mapped[int | None] = mapped_column(ForeignKey("classes.id"))
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id"))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MonthlyExamGrade(Base):
    __tablename__ = "monthly_exam_grades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    exam_date: Mapped[datetime] = mapped_column(DateTime)
    grade: Mapped[int] = mapped_column(Integer)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
