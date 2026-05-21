import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import and_, distinct, func, or_
from sqlalchemy.orm import Session

from app.core.security import get_current_user, require_admin, require_student
from app.db.models import (
    AttemptStatus,
    Class,
    Group,
    Roadmap,
    RoadmapAssignment,
    RoadmapAttempt,
    RoadmapItem,
    RoadmapMini,
    StudentProfile,
    User,
    UserRole,
)
from app.db.session import get_db
from app.schemas.assignments import RoadmapAssignRequest
from app.schemas.attempts import SubmitAttemptRequest
from app.schemas.roadmap import NextQuestionRequest, RoadmapCreateRequest

router = APIRouter()

UPLOAD_ROOT = Path(__file__).resolve().parents[2] / "uploads" / "roadmaps"
ALLOWED_MEDIA_TYPES = {"application/pdf", "image/jpeg", "image/png", "image/webp", "image/gif"}


def _normalize_answer(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


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


def _serialize_roadmap_item(item: RoadmapItem) -> dict:
    return {
        "id": item.id,
        "roadmap_id": item.roadmap_id,
        "mini_roadmap_id": item.mini_roadmap_id,
        "order_in_mini": item.order_in_mini,
        "topic": item.topic,
        "sequence_index": item.sequence_index,
        "question_text": item.question_text,
        "media_type": item.media_type,
        "media_path": item.media_path,
        "choices": item.choices or [],
    }


def _serialize_mini_roadmap(mini: RoadmapMini) -> dict:
    return {
        "id": mini.id,
        "roadmap_id": mini.roadmap_id,
        "title": mini.title or mini.question_type,
        "sequence_index": mini.sequence_index,
    }


def _ensure_upload_dir() -> Path:
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    return UPLOAD_ROOT


def _normalize_choice(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _match_choice(answer: str, choices: list[str]) -> str | None:
    normalized_answer = _normalize_choice(answer)
    for choice in choices:
        if _normalize_choice(choice) == normalized_answer:
            return choice
    return None


@router.post("/admin/upload")
def upload_roadmap_media(
    file: UploadFile = File(...),
    _: User = Depends(require_admin),
):
    if file.content_type not in ALLOWED_MEDIA_TYPES:
        raise HTTPException(status_code=400, detail="Only images or PDF files are allowed")

    upload_dir = _ensure_upload_dir()
    suffix = Path(file.filename or "").suffix
    filename = f"{uuid4().hex}{suffix}"
    destination = upload_dir / filename

    with destination.open("wb") as output:
        shutil.copyfileobj(file.file, output)

    media_type = "image" if file.content_type.startswith("image/") else "pdf"
    return {"media_path": filename, "media_type": media_type}


@router.get("/media/{filename}")
def get_roadmap_media(
    filename: str,
    _: User = Depends(get_current_user),
):
    file_path = _ensure_upload_dir() / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)


@router.post("/admin/create")
def create_roadmap(
    payload: RoadmapCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if not payload.title.strip():
        raise HTTPException(status_code=400, detail="Roadmap title is required")
    if not payload.minis:
        raise HTTPException(status_code=400, detail="Add at least one mini roadmap")

    roadmap = Roadmap(
        title=payload.title.strip(),
        pdf_id=None,
        created_by=current_user.id,
    )
    db.add(roadmap)
    db.flush()

    for mini_index, mini in enumerate(payload.minis, start=1):
        if not mini.title.strip():
            raise HTTPException(status_code=400, detail="Mini roadmap title is required")
        if not mini.questions:
            raise HTTPException(status_code=400, detail="Each mini roadmap needs questions")

        roadmap_mini = RoadmapMini(
            roadmap_id=roadmap.id,
            title=mini.title.strip(),
            question_type="manual",
            sequence_index=mini_index,
        )
        db.add(roadmap_mini)
        db.flush()

        for question_index, question in enumerate(mini.questions, start=1):
            has_text = bool(question.question_text and question.question_text.strip())
            has_media = bool(question.media_path)
            if has_text == has_media:
                raise HTTPException(
                    status_code=400,
                    detail="Each question must have either text or a media file",
                )
            choices = [choice.strip() for choice in question.choices if choice.strip()]
            if len(choices) < 2:
                raise HTTPException(status_code=400, detail="Each question needs at least 2 choices")
            matched_answer = _match_choice(question.answer_key, choices)
            if not matched_answer:
                raise HTTPException(status_code=400, detail="Answer key must match one of the choices")
            if has_media and question.media_type not in {"image", "pdf"}:
                raise HTTPException(status_code=400, detail="Media type must be image or pdf")

            db.add(
                RoadmapItem(
                    roadmap_id=roadmap.id,
                    mini_roadmap_id=roadmap_mini.id,
                    topic=mini.title.strip(),
                    question_type="manual",
                    difficulty="manual",
                    sequence_index=mini_index,
                    order_in_mini=question_index,
                    question_text=question.question_text.strip() if has_text else None,
                    media_type=question.media_type if has_media else None,
                    media_path=question.media_path if has_media else None,
                    choices=choices,
                    answer_key=matched_answer,
                )
            )

    db.commit()
    return {"roadmap_id": roadmap.id}


@router.post("/next-question")
def next_question(
    payload: NextQuestionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student),
):
    mini = db.get(RoadmapMini, payload.mini_roadmap_id)
    if not mini:
        raise HTTPException(status_code=404, detail="Mini roadmap not found")

    items = (
        db.query(RoadmapItem)
        .filter(RoadmapItem.mini_roadmap_id == payload.mini_roadmap_id)
        .order_by(RoadmapItem.order_in_mini.asc())
        .all()
    )
    if not items:
        raise HTTPException(status_code=404, detail="No questions available")

    correct_item_ids = {
        attempt.roadmap_item_id
        for attempt in db.query(RoadmapAttempt)
        .filter(
            RoadmapAttempt.student_id == current_user.id,
            RoadmapAttempt.mini_roadmap_id == payload.mini_roadmap_id,
            RoadmapAttempt.status == AttemptStatus.correct,
        )
        .all()
    }

    for item in items:
        if item.id not in correct_item_ids:
            return {"item": _serialize_roadmap_item(item)}

    return {"completed": True}


@router.post("/submit")
def submit_attempt(
    payload: SubmitAttemptRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student),
):
    item = db.get(RoadmapItem, payload.roadmap_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Roadmap item not found")

    if not _is_student_assigned(db, item.roadmap_id, current_user):
        raise HTTPException(status_code=403, detail="Not assigned to this roadmap")

    if payload.mini_roadmap_id and item.mini_roadmap_id != payload.mini_roadmap_id:
        raise HTTPException(status_code=400, detail="Question does not belong to this mini roadmap")

    choices = item.choices or []
    if not choices:
        raise HTTPException(status_code=400, detail="No choices available for this question")
    if not item.answer_key:
        raise HTTPException(status_code=400, detail="Answer key is missing")

    selected = _normalize_answer(payload.selected_answer)
    expected = _normalize_answer(item.answer_key)
    is_correct = selected == expected
    if not is_correct and payload.selected_answer and payload.selected_answer.isalpha() and len(payload.selected_answer) == 1:
        index = ord(payload.selected_answer.upper()) - ord("A")
        if 0 <= index < len(choices):
            is_correct = _normalize_answer(choices[index]) == expected
    if not is_correct:
        matched_choice = _match_choice(payload.selected_answer, choices)
        if matched_choice and _normalize_answer(matched_choice) == expected:
            is_correct = True

    attempt_no = (
        db.query(func.count(RoadmapAttempt.id))
        .filter(
            RoadmapAttempt.student_id == current_user.id,
            RoadmapAttempt.roadmap_item_id == item.id,
        )
        .scalar()
        or 0
    ) + 1

    status = AttemptStatus.correct if is_correct else AttemptStatus.incorrect
    db.add(
        RoadmapAttempt(
            student_id=current_user.id,
            roadmap_item_id=item.id,
            mini_roadmap_id=item.mini_roadmap_id,
            attempt_no=attempt_no,
            status=status,
        )
    )

    db.commit()
    return {"status": status.value, "is_correct": is_correct}


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

    minis = (
        db.query(RoadmapMini)
        .filter(RoadmapMini.roadmap_id == roadmap_id)
        .order_by(RoadmapMini.sequence_index.asc())
        .all()
    )
    if minis:
        return [_serialize_mini_roadmap(mini) for mini in minis]

    items = (
        db.query(RoadmapItem)
        .filter(RoadmapItem.roadmap_id == roadmap_id)
        .order_by(RoadmapItem.sequence_index.asc())
        .all()
    )
    return [_serialize_roadmap_item(item) for item in items]


@router.get("/progress")
def student_roadmap_progress(
    roadmap_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student),
):
    if not _is_student_assigned(db, roadmap_id, current_user):
        raise HTTPException(status_code=403, detail="Not assigned to this roadmap")

    total_items = db.query(func.count(RoadmapMini.id)).filter(RoadmapMini.roadmap_id == roadmap_id).scalar()
    if not total_items:
        total_items = db.query(func.count(RoadmapItem.id)).filter(RoadmapItem.roadmap_id == roadmap_id).scalar()
    if not total_items:
        return {"roadmap_id": roadmap_id, "total_items": 0, "progress": 0}

    if db.query(func.count(RoadmapMini.id)).filter(RoadmapMini.roadmap_id == roadmap_id).scalar():
        correct_count = (
            db.query(func.count(distinct(RoadmapAttempt.mini_roadmap_id)))
            .join(RoadmapItem, RoadmapItem.id == RoadmapAttempt.roadmap_item_id)
            .filter(
                RoadmapItem.roadmap_id == roadmap_id,
                RoadmapAttempt.student_id == current_user.id,
                RoadmapAttempt.status == AttemptStatus.correct,
            )
            .scalar()
        )
    else:
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
    total_items = db.query(func.count(RoadmapMini.id)).filter(RoadmapMini.roadmap_id == roadmap_id).scalar()
    if not total_items:
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

    if db.query(func.count(RoadmapMini.id)).filter(RoadmapMini.roadmap_id == roadmap_id).scalar():
        correct_subquery = (
            db.query(
                RoadmapAttempt.student_id.label("student_id"),
                func.count(distinct(RoadmapAttempt.mini_roadmap_id)).label("correct_count"),
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
    else:
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
    roadmaps = db.query(Roadmap).order_by(Roadmap.created_at.desc()).all()
    response = []
    for roadmap in roadmaps:
        total_items = db.query(func.count(RoadmapMini.id)).filter(RoadmapMini.roadmap_id == roadmap.id).scalar()
        if not total_items:
            total_items = db.query(func.count(RoadmapItem.id)).filter(RoadmapItem.roadmap_id == roadmap.id).scalar()

        if db.query(func.count(RoadmapMini.id)).filter(RoadmapMini.roadmap_id == roadmap.id).scalar():
            correct_items = (
                db.query(func.count(distinct(RoadmapAttempt.mini_roadmap_id)))
                .join(RoadmapItem, RoadmapItem.id == RoadmapAttempt.roadmap_item_id)
                .filter(
                    RoadmapItem.roadmap_id == roadmap.id,
                    RoadmapAttempt.status == AttemptStatus.correct,
                )
                .scalar()
            )
        else:
            correct_items = (
                db.query(func.count(distinct(RoadmapAttempt.roadmap_item_id)))
                .join(RoadmapItem, RoadmapItem.id == RoadmapAttempt.roadmap_item_id)
                .filter(
                    RoadmapItem.roadmap_id == roadmap.id,
                    RoadmapAttempt.status == AttemptStatus.correct,
                )
                .scalar()
            )

        completed = correct_items or 0
        percent = int((completed / total_items) * 100) if total_items else 0
        response.append(
            {
                "roadmap_id": roadmap.id,
                "title": roadmap.title,
                "total_items": total_items,
                "completed_items": completed,
                "progress": percent,
            }
        )
    return response
