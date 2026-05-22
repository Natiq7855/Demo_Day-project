from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import require_admin
from app.db.models import Pdf, PdfChunk, User, UserRole, UserStatus
from app.db.session import get_db
from app.services.pdf_extractor import chunk_text, extract_text_by_page, pdf_text_stats

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


@router.get("/pdfs")
def list_pdfs(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    pdfs = db.query(Pdf).order_by(Pdf.created_at.desc()).all()
    response = []
    for item in pdfs:
        stats = (
            db.query(
                func.count(PdfChunk.id).label("chunks"),
                func.max(PdfChunk.page_end).label("page_max"),
                func.min(PdfChunk.page_start).label("page_min"),
            )
            .filter(PdfChunk.pdf_id == item.id)
            .one()
        )
        response.append(
            {
                "id": item.id,
                "title": item.title,
                "created_at": item.created_at,
                "chunks": stats.chunks or 0,
                "page_min": stats.page_min,
                "page_max": stats.page_max,
            }
        )
    return response


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
    text_stats = pdf_text_stats(pages)
    if text_stats["non_empty_pages"] == 0:
        db.rollback()
        file_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail=(
                "No readable text found in this PDF. "
                "Use a text-based PDF (not a scan/photo). OCR is not enabled in this demo."
            ),
        )

    chunk_count = 0
    for index, (chunk, page_start, page_end) in enumerate(chunk_text(pages), start=1):
        if not chunk.strip():
            continue
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

    if chunk_count == 0:
        db.rollback()
        file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="PDF uploaded but no indexable chunks were created")

    db.commit()
    return {
        "pdf_id": pdf.id,
        "chunks": chunk_count,
        "pages": text_stats["pages"],
        "non_empty_pages": text_stats["non_empty_pages"],
        "total_chars": text_stats["total_chars"],
        "page_min": 1,
        "page_max": text_stats["pages"],
    }


@router.get("/download-pdf/{pdf_id}")
def download_pdf(
    pdf_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    pdf = db.get(Pdf, pdf_id)
    if not pdf:
        raise HTTPException(status_code=404, detail="PDF not found")

    file_path = Path(pdf.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(path=file_path, filename=file_path.name)
