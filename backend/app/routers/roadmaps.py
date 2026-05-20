from fastapi import APIRouter, Depends, HTTPException
from groq import APIError
from sqlalchemy import and_, distinct, func, or_
from sqlalchemy.orm import Session

from app.core.security import require_admin, require_student
from app.core.security import get_current_user
from app.db.models import (
    AttemptStatus,
    AiQuestion,
    Class,
    PdfChunk,
    Group,
    RoadmapAttempt,
    RoadmapAssignment,
    RoadmapItem,
    Roadmap,
    RoadmapPhase,
    RoadmapState,
    StudentProfile,
    User,
    UserRole,
)
from app.db.session import get_db
from app.schemas.assignments import RoadmapAssignRequest
from app.schemas.attempts import SubmitAttemptRequest
from app.schemas.roadmap import NextQuestionRequest, RoadmapGenerateRequest
from app.services.adaptive_engine import generate_next_question
from app.services.roadmap_generator import generate_roadmap

router = APIRouter()


def _get_pdf_context(
    db: Session,
    pdf_id: int,
    page_start: int | None,
    page_end: int | None,
) -> str:
    query = db.query(PdfChunk).filter(PdfChunk.pdf_id == pdf_id)
    if page_start is not None and page_end is not None:
        query = query.filter(
            PdfChunk.page_end >= page_start,
            PdfChunk.page_start <= page_end,
        )
    chunks = query.order_by(PdfChunk.chunk_index).all()
    return "\n".join(chunk.content_text for chunk in chunks)


def _get_roadmap_context(db: Session, roadmap_item_id: int) -> str:
    roadmap = (
        db.query(Roadmap)
        .join(RoadmapItem, RoadmapItem.roadmap_id == Roadmap.id)
        .filter(RoadmapItem.id == roadmap_item_id)
        .one_or_none()
    )
    if not roadmap:
        return ""
    return _get_pdf_context(db, roadmap.pdf_id, roadmap.page_start, roadmap.page_end)


def _get_student_targets(current_user: User) -> dict[str, list[int]]:
    profile = current_user.student_profile
    if not profile:
        return {"student": [current_user.id], "class": [], "group": []}
    return {
        "student": [current_user.id],
        "class": [profile.class_id] if profile.class_id else [],
        "group": [profile.group_id] if profile.group_id else [],
    }


def _validate_assignment_target(db: Session, target_type: str, target_id: int) -> None:
    if target_type == "class":
        if not db.get(Class, target_id):
            raise HTTPException(status_code=404, detail="Class not found")
    elif target_type == "group":
        if not db.get(Group, target_id):
            raise HTTPException(status_code=404, detail="Group not found")
    elif target_type == "student":
        user = db.get(User, target_id)
        if not user or user.role != UserRole.student:
            raise HTTPException(status_code=404, detail="Student not found")
    else:
        raise HTTPException(status_code=400, detail="Invalid target type")


def _is_student_assigned(db: Session, roadmap_id: int, current_user: User) -> bool:
    targets = _get_student_targets(current_user)
    assignment = (
        db.query(RoadmapAssignment)
        .filter(
            RoadmapAssignment.roadmap_id == roadmap_id,
            or_(
                and_(
                    RoadmapAssignment.target_type == "student",
                    RoadmapAssignment.target_id.in_(targets["student"]),
                ),
                and_(
                    RoadmapAssignment.target_type == "class",
                    RoadmapAssignment.target_id.in_(targets["class"]),
                ),
                and_(
                    RoadmapAssignment.target_type == "group",
                    RoadmapAssignment.target_id.in_(targets["group"]),
                ),
            ),
        )
        .one_or_none()
    )
    return assignment is not None


def _serialize_question(question: AiQuestion | None) -> dict | None:
    if not question:
        return None
    return {
        "id": question.id,
        "type": question.type_label,
        "difficulty": question.difficulty,
        "text": question.question_text,
        "choices": question.choices,
        "answer_key": question.answer_key,
        "hint": question.hint,
        "explanation": question.explanation,
    }


def _serialize_roadmap_item(db: Session, item: RoadmapItem) -> dict:
    question = (
        db.query(AiQuestion)
        .filter(AiQuestion.roadmap_item_id == item.id)
        .order_by(AiQuestion.created_at.asc())
        .first()
    )
    return {
        "id": item.id,
        "roadmap_id": item.roadmap_id,
        "topic": item.topic,
        "question_type": item.question_type,
        "difficulty": item.difficulty,
        "sequence_index": item.sequence_index,
        "metadata": item.metadata_,
        "question": _serialize_question(question),
    }


@router.post("/generate")
def create_roadmap(
    payload: RoadmapGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    chunk_context = _get_pdf_context(db, payload.pdf_id, payload.page_start, payload.page_end)
    if not chunk_context:
        raise HTTPException(status_code=400, detail="No PDF content found for selection")

    try:
        roadmap_id = generate_roadmap(
            db=db,
            pdf_id=payload.pdf_id,
            title=payload.title,
            chunk_context=chunk_context,
            created_by=current_user.id,
            page_start=payload.page_start,
            page_end=payload.page_end,
        )
    except APIError as error:
        db.rollback()
        raise HTTPException(status_code=502, detail=f"Groq roadmap generation failed: {error}") from error
    except Exception as error:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Roadmap generation failed: {error}") from error
    return {"roadmap_id": roadmap_id}


@router.post("/next-question")
def next_question(
    payload: NextQuestionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student),
):
    response = generate_next_question(
        db=db,
        student_id=current_user.id,
        roadmap_item_id=payload.roadmap_item_id,
        chunk_context=_get_roadmap_context(db, payload.roadmap_item_id),
    )
    return response


@router.post("/submit")
def submit_attempt(
    payload: SubmitAttemptRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student),
):
    item = db.get(RoadmapItem, payload.roadmap_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Roadmap item not found")

    state = (
        db.query(RoadmapState)
        .filter(
            RoadmapState.student_id == current_user.id,
            RoadmapState.roadmap_item_id == payload.roadmap_item_id,
        )
        .one_or_none()
    )
    if not state:
        state = RoadmapState(
            student_id=current_user.id,
            roadmap_item_id=payload.roadmap_item_id,
            consecutive_failures=0,
            phase=RoadmapPhase.A,
            last_question_id=payload.question_id,
        )
        db.add(state)
        db.flush()
    else:
        state.last_question_id = payload.question_id

    attempt_no = state.consecutive_failures + 1
    status = AttemptStatus.correct if payload.is_correct else AttemptStatus.incorrect
    db.add(
        RoadmapAttempt(
            student_id=current_user.id,
            roadmap_item_id=payload.roadmap_item_id,
            attempt_no=attempt_no,
            status=status,
        )
    )

    if payload.is_correct:
        state.consecutive_failures = 0
        state.phase = RoadmapPhase.A
    else:
        state.consecutive_failures += 1

    db.commit()
    return {"status": status.value, "consecutive_failures": state.consecutive_failures}


@router.post("/assign")
def assign_roadmap(
    payload: RoadmapAssignRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    roadmap = db.get(Roadmap, payload.roadmap_id)
    if not roadmap:
        raise HTTPException(status_code=404, detail="Roadmap not found")

    _validate_assignment_target(db, payload.target_type, payload.target_id)

    db.add(
        RoadmapAssignment(
            roadmap_id=payload.roadmap_id,
            target_type=payload.target_type,
            target_id=payload.target_id,
        )
    )
    db.commit()
    return {"status": "assigned"}


@router.get("/assigned")
def list_assigned_roadmaps(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student),
):
    targets = _get_student_targets(current_user)
    assignments = (
        db.query(RoadmapAssignment.roadmap_id)
        .filter(
            or_(
                and_(
                    RoadmapAssignment.target_type == "student",
                    RoadmapAssignment.target_id.in_(targets["student"]),
                ),
                and_(
                    RoadmapAssignment.target_type == "class",
                    RoadmapAssignment.target_id.in_(targets["class"]),
                ),
                and_(
                    RoadmapAssignment.target_type == "group",
                    RoadmapAssignment.target_id.in_(targets["group"]),
                ),
            )
        )
        .subquery()
    )
    roadmaps = (
        db.query(Roadmap)
        .join(assignments, Roadmap.id == assignments.c.roadmap_id)
        .order_by(Roadmap.created_at.desc())
        .all()
    )
    return [{"id": item.id, "title": item.title} for item in roadmaps]


@router.get("/{roadmap_id}/items")
def list_roadmap_items(
    roadmap_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    roadmap = db.get(Roadmap, roadmap_id)
    if not roadmap:
        raise HTTPException(status_code=404, detail="Roadmap not found")

    if current_user.role == UserRole.student and not _is_student_assigned(db, roadmap_id, current_user):
        raise HTTPException(status_code=403, detail="Not assigned to this roadmap")

    items = (
        db.query(RoadmapItem)
        .filter(RoadmapItem.roadmap_id == roadmap_id)
        .order_by(RoadmapItem.sequence_index.asc())
        .all()
    )
    return [_serialize_roadmap_item(db, item) for item in items]


@router.get("/progress")
def student_roadmap_progress(
    roadmap_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student),
):
    if not _is_student_assigned(db, roadmap_id, current_user):
        raise HTTPException(status_code=403, detail="Not assigned to this roadmap")

    total_items = db.query(func.count(RoadmapItem.id)).filter(RoadmapItem.roadmap_id == roadmap_id).scalar()
    if not total_items:
        return {"roadmap_id": roadmap_id, "total_items": 0, "progress": 0}

    correct_count = (
        db.query(func.count(distinct(RoadmapAttempt.roadmap_item_id)))
        .join(RoadmapItem, RoadmapItem.id == RoadmapAttempt.roadmap_item_id)
        .filter(
            RoadmapItem.roadmap_id == roadmap_id,
            RoadmapAttempt.student_id == current_user.id,
            RoadmapAttempt.status == AttemptStatus.correct,
        )
        .scalar()
    )

    percent = int(((correct_count or 0) / total_items) * 100)
    return {"roadmap_id": roadmap_id, "total_items": total_items, "progress": percent}


@router.get("/admin/progress")
def roadmap_progress(
    roadmap_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    total_items = db.query(func.count(RoadmapItem.id)).filter(RoadmapItem.roadmap_id == roadmap_id).scalar()
    if not total_items:
        return {"roadmap_id": roadmap_id, "total_items": 0, "students": []}

    assigned_students = set()

    assignment_rows = db.query(RoadmapAssignment).filter(RoadmapAssignment.roadmap_id == roadmap_id).all()
    for assignment in assignment_rows:
        if assignment.target_type == "student":
            assigned_students.add(assignment.target_id)
        elif assignment.target_type == "class":
            students = (
                db.query(StudentProfile.user_id)
                .filter(StudentProfile.class_id == assignment.target_id)
                .all()
            )
            assigned_students.update(student_id for (student_id,) in students)
        elif assignment.target_type == "group":
            students = (
                db.query(StudentProfile.user_id)
                .filter(StudentProfile.group_id == assignment.target_id)
                .all()
            )
            assigned_students.update(student_id for (student_id,) in students)

    if not assigned_students:
        return {"roadmap_id": roadmap_id, "total_items": total_items, "students": []}

    correct_subquery = (
        db.query(
            RoadmapAttempt.student_id.label("student_id"),
            func.count(distinct(RoadmapAttempt.roadmap_item_id)).label("correct_count"),
        )
        .join(RoadmapItem, RoadmapItem.id == RoadmapAttempt.roadmap_item_id)
        .filter(
            RoadmapItem.roadmap_id == roadmap_id,
            RoadmapAttempt.status == AttemptStatus.correct,
            RoadmapAttempt.student_id.in_(assigned_students),
        )
        .group_by(RoadmapAttempt.student_id)
        .subquery()
    )

    students = (
        db.query(User.id, User.email, correct_subquery.c.correct_count)
        .outerjoin(correct_subquery, User.id == correct_subquery.c.student_id)
        .filter(User.id.in_(assigned_students))
        .all()
    )

    payload = []
    for student_id, email, correct_count in students:
        completed = correct_count or 0
        percent = int((completed / total_items) * 100)
        payload.append({"student_id": student_id, "email": email, "progress": percent})

    return {"roadmap_id": roadmap_id, "total_items": total_items, "students": payload}


@router.get("/admin/summary")
def roadmap_summary(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    totals = (
        db.query(Roadmap.id, Roadmap.title, func.count(RoadmapItem.id).label("total_items"))
        .join(RoadmapItem, RoadmapItem.roadmap_id == Roadmap.id)
        .group_by(Roadmap.id)
        .subquery()
    )

    correct = (
        db.query(
            RoadmapItem.roadmap_id.label("roadmap_id"),
            func.count(distinct(RoadmapAttempt.roadmap_item_id)).label("correct_items"),
        )
        .join(RoadmapAttempt, RoadmapAttempt.roadmap_item_id == RoadmapItem.id)
        .filter(RoadmapAttempt.status == AttemptStatus.correct)
        .group_by(RoadmapItem.roadmap_id)
        .subquery()
    )

    rows = (
        db.query(totals.c.id, totals.c.title, totals.c.total_items, correct.c.correct_items)
        .outerjoin(correct, totals.c.id == correct.c.roadmap_id)
        .all()
    )

    response = []
    for roadmap_id, title, total_items, correct_items in rows:
        completed = correct_items or 0
        percent = int((completed / total_items) * 100) if total_items else 0
        response.append(
            {
                "roadmap_id": roadmap_id,
                "title": title,
                "total_items": total_items,
                "completed_items": completed,
                "progress": percent,
            }
        )
    return response
