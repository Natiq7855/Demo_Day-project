from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import require_admin, require_student
from app.db.models import (
    AttemptStatus,
    PdfChunk,
    RoadmapAttempt,
    RoadmapItem,
    Roadmap,
    RoadmapPhase,
    RoadmapState,
    User,
)
from app.db.session import get_db
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


@router.post("/generate")
def create_roadmap(
    payload: RoadmapGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    chunk_context = _get_pdf_context(db, payload.pdf_id, payload.page_start, payload.page_end)
    if not chunk_context:
        raise HTTPException(status_code=400, detail="No PDF content found for selection")

    roadmap_id = generate_roadmap(
        db=db,
        pdf_id=payload.pdf_id,
        title=payload.title,
        chunk_context=chunk_context,
        created_by=current_user.id,
        page_start=payload.page_start,
        page_end=payload.page_end,
    )
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
        raise HTTPException(status_code=404, detail="Roadmap state not found")

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
