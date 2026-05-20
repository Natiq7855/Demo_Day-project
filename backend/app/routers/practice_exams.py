from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import require_admin, require_student
from app.db.models import Class, Group, PracticeExam, PracticeExamAssignment, PracticeExamAttempt, User, UserRole
from app.db.session import get_db
from app.schemas.assignments import PracticeExamAssignRequest
from app.schemas.practice_exams import PracticeExamSubmitRequest

router = APIRouter()


def _get_student_target_ids(current_user: User) -> dict[str, list[int]]:
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


@router.post("/admin/upload")
def upload_practice_exam(
    title: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="File is required")

    storage_dir = Path(settings.media_root) / "practice_exams"
    storage_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    safe_name = f"{timestamp}_{file.filename.replace(' ', '_')}"
    file_path = storage_dir / safe_name

    content = file.file.read()
    file.file.close()
    file_path.write_bytes(content)

    exam = PracticeExam(title=title, file_path=str(file_path), uploaded_by=current_user.id)
    db.add(exam)
    db.commit()
    return {"id": exam.id, "title": exam.title}


@router.get("/admin/list")
def list_practice_exams_admin(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    exams = db.query(PracticeExam).order_by(PracticeExam.created_at.desc()).all()
    return [{"id": item.id, "title": item.title, "created_at": item.created_at} for item in exams]


@router.get("/student/list")
def list_practice_exams(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student),
):
    targets = _get_student_target_ids(current_user)
    assignments = (
        db.query(PracticeExamAssignment.practice_exam_id)
        .filter(
            or_(
                and_(
                    PracticeExamAssignment.target_type == "student",
                    PracticeExamAssignment.target_id.in_(targets["student"]),
                ),
                and_(
                    PracticeExamAssignment.target_type == "class",
                    PracticeExamAssignment.target_id.in_(targets["class"]),
                ),
                and_(
                    PracticeExamAssignment.target_type == "group",
                    PracticeExamAssignment.target_id.in_(targets["group"]),
                ),
            )
        )
        .subquery()
    )
    exams = (
        db.query(PracticeExam)
        .join(assignments, PracticeExam.id == assignments.c.practice_exam_id)
        .order_by(PracticeExam.created_at.desc())
        .all()
    )
    return [{"id": item.id, "title": item.title, "created_at": item.created_at} for item in exams]


@router.post("/student/submit")
def submit_practice_exam(
    payload: PracticeExamSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student),
):
    exam = db.get(PracticeExam, payload.practice_exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Practice exam not found")

    attempt = PracticeExamAttempt(
        practice_exam_id=payload.practice_exam_id,
        student_id=current_user.id,
        score=payload.score,
    )
    db.add(attempt)
    db.commit()
    return {"status": "submitted"}


@router.post("/admin/assign")
def assign_practice_exam(
    payload: PracticeExamAssignRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    exam = db.get(PracticeExam, payload.practice_exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Practice exam not found")

    _validate_assignment_target(db, payload.target_type, payload.target_id)

    db.add(
        PracticeExamAssignment(
            practice_exam_id=payload.practice_exam_id,
            target_type=payload.target_type,
            target_id=payload.target_id,
        )
    )
    db.commit()
    return {"status": "assigned"}


@router.get("/admin/download/{exam_id}")
def download_practice_exam_admin(
    exam_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    exam = db.get(PracticeExam, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Practice exam not found")

    file_path = Path(exam.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(path=file_path, filename=file_path.name)


@router.get("/student/download/{exam_id}")
def download_practice_exam(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student),
):
    targets = _get_student_target_ids(current_user)
    assignment = (
        db.query(PracticeExamAssignment)
        .filter(
            PracticeExamAssignment.practice_exam_id == exam_id,
            or_(
                and_(
                    PracticeExamAssignment.target_type == "student",
                    PracticeExamAssignment.target_id.in_(targets["student"]),
                ),
                and_(
                    PracticeExamAssignment.target_type == "class",
                    PracticeExamAssignment.target_id.in_(targets["class"]),
                ),
                and_(
                    PracticeExamAssignment.target_type == "group",
                    PracticeExamAssignment.target_id.in_(targets["group"]),
                ),
            ),
        )
        .one_or_none()
    )
    if not assignment:
        raise HTTPException(status_code=403, detail="Not assigned to this exam")

    exam = db.get(PracticeExam, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Practice exam not found")

    file_path = Path(exam.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(path=file_path, filename=file_path.name)
