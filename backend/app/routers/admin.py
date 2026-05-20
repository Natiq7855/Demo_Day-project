from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import require_admin
from app.db.models import Pdf, PdfChunk, User, UserRole, UserStatus
from app.db.session import get_db
from app.services.pdf_extractor import chunk_text, extract_text_by_page

router = APIRouter()


@router.get("/pending-users")
def list_pending_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    users = db.query(User).filter(User.status == UserStatus.pending).all()
    return [{"id": user.id, "email": user.email, "role": user.role.value} for user in users]


@router.get("/students")
def list_students(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    users = db.query(User).filter(User.role == UserRole.student).all()
    return [{"id": user.id, "email": user.email, "status": user.status.value} for user in users]


@router.post("/upload-pdf")
def upload_pdf(
    title: str = Form(...),
    chapter: str | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    storage_dir = Path(settings.media_root) / "pdfs"
    storage_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    safe_name = f"{timestamp}_{file.filename.replace(' ', '_')}"
    file_path = storage_dir / safe_name

    content = file.file.read()
    file.file.close()
    file_path.write_bytes(content)

    pdf = Pdf(title=title, file_path=str(file_path), uploaded_by=current_user.id)
    db.add(pdf)
    db.flush()

    pages = extract_text_by_page(str(file_path))
    chunk_count = 0
    for index, (chunk, page_start, page_end) in enumerate(chunk_text(pages), start=1):
        chunk_count += 1
        db.add(
            PdfChunk(
                pdf_id=pdf.id,
                chapter=chapter,
                page_start=page_start,
                page_end=page_end,
                chunk_index=index,
                content_text=chunk,
            )
        )

    db.commit()
    return {"pdf_id": pdf.id, "chunks": chunk_count}
