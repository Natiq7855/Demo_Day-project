from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import require_admin, require_student
from app.db.models import PracticeExam, PracticeExamAttempt, User
from app.db.session import get_db
from app.schemas.practice_exams import PracticeExamSubmitRequest

router = APIRouter()


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


@router.get("/student/list")
def list_practice_exams(
    db: Session = Depends(get_db),
    _: User = Depends(require_student),
):
    exams = db.query(PracticeExam).order_by(PracticeExam.created_at.desc()).all()
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
