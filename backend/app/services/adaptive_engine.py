import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import AiQuestion, RoadmapItem, RoadmapPhase, RoadmapState
from app.services.gemini_client import create_json_completion
from app.utils.json_schema import QUESTION_SCHEMA


def _select_phase(state: RoadmapState) -> RoadmapPhase:
    if state.phase == RoadmapPhase.RETEST:
        return RoadmapPhase.RETEST
    if state.consecutive_failures == 0:
        return RoadmapPhase.A
    if state.consecutive_failures == 1:
        return RoadmapPhase.A1
    if state.consecutive_failures == 2:
        return RoadmapPhase.HINT
    return RoadmapPhase.EXPLAIN


def _build_messages(roadmap_item: RoadmapItem, phase: RoadmapPhase, chunk_context: str):
    system = (
        "You are an education assistant. Return only JSON matching the provided schema."
    )
    user = (
        "Generate a question for the roadmap item below. "
        "If phase is HINT, provide a hint without the answer. "
        "If phase is EXPLAIN, provide a full step-by-step explanation and a new question. "
        "If phase is RETEST, generate a brand-new question of the same type.\n\n"
        f"Topic: {roadmap_item.topic}\n"
        f"Question type: {roadmap_item.question_type}\n"
        f"Difficulty: {roadmap_item.difficulty}\n"
        f"Phase: {phase.value}\n"
        f"Context: {chunk_context}\n"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def generate_next_question(db: Session, student_id: int, roadmap_item_id: int, chunk_context: str):
    roadmap_item = db.get(RoadmapItem, roadmap_item_id)
    if not roadmap_item:
        raise ValueError("Roadmap item not found")

    state = (
        db.query(RoadmapState)
        .filter(
            RoadmapState.student_id == student_id,
            RoadmapState.roadmap_item_id == roadmap_item_id,
        )
        .one_or_none()
    )

    if not state:
        state = RoadmapState(
            student_id=student_id,
            roadmap_item_id=roadmap_item_id,
            consecutive_failures=0,
            phase=RoadmapPhase.A,
            updated_at=datetime.utcnow(),
        )
        db.add(state)
        db.flush()

    phase = _select_phase(state)
    messages = _build_messages(roadmap_item, phase, chunk_context)
    content = create_json_completion(messages, QUESTION_SCHEMA)
    payload = json.loads(content)

    question = AiQuestion(
        roadmap_item_id=roadmap_item_id,
        student_id=student_id,
        type_label=payload["question"]["type"],
        difficulty=payload["question"]["difficulty"],
        question_text=payload["question"]["text"],
        choices=payload["question"].get("choices"),
        answer_key=payload["question"].get("answer_key"),
        hint=payload.get("hint"),
        explanation=payload.get("explanation"),
    )
    db.add(question)
    db.flush()

    state.last_question_id = question.id
    state.updated_at = datetime.utcnow()
    if phase == RoadmapPhase.EXPLAIN:
        state.phase = RoadmapPhase.RETEST
    elif phase == RoadmapPhase.RETEST:
        state.phase = RoadmapPhase.A
    else:
        state.phase = phase

    db.commit()
    return payload
