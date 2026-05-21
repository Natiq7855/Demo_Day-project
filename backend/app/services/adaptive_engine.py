import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import AiQuestion, RoadmapItem, RoadmapMini, RoadmapPhase, RoadmapState
from app.services.groq_client import create_json_completion
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


def _serialize_ai_question(question: AiQuestion, hint: str | None, explanation: str | None) -> dict:
    return {
        "question": {
            "id": question.id,
            "type": question.type_label,
            "text": question.question_text,
            "choices": question.choices or [],
            "answer_key": question.answer_key,
            "difficulty": question.difficulty,
        },
        "hint": hint,
        "explanation": explanation,
    }


def generate_next_question(
    db: Session,
    student_id: int,
    roadmap_item_id: int | None,
    mini_roadmap_id: int | None,
    chunk_context: str,
):
    roadmap_item = db.get(RoadmapItem, roadmap_item_id) if roadmap_item_id else None
    if mini_roadmap_id:
        roadmap_mini = db.get(RoadmapMini, mini_roadmap_id)
        if not roadmap_mini:
            raise ValueError("Mini roadmap not found")
        items = (
            db.query(RoadmapItem)
            .filter(RoadmapItem.mini_roadmap_id == mini_roadmap_id)
            .order_by(RoadmapItem.order_in_mini.asc())
            .all()
        )
        if not items:
            raise ValueError("Mini roadmap has no questions")
        roadmap_item = items[0]
    if not roadmap_item:
        raise ValueError("Roadmap item not found")

    state_query = db.query(RoadmapState).filter(RoadmapState.student_id == student_id)
    if mini_roadmap_id:
        state_query = state_query.filter(RoadmapState.mini_roadmap_id == mini_roadmap_id)
    else:
        state_query = state_query.filter(RoadmapState.roadmap_item_id == roadmap_item.id)
    state = state_query.one_or_none()

    if not state:
        state = RoadmapState(
            student_id=student_id,
            roadmap_item_id=roadmap_item.id,
            mini_roadmap_id=mini_roadmap_id,
            consecutive_failures=0,
            phase=RoadmapPhase.A,
            updated_at=datetime.utcnow(),
            step_index=0,
        )
        db.add(state)
        db.flush()

    if mini_roadmap_id:
        step_index = min(state.consecutive_failures, 3)
        items = (
            db.query(RoadmapItem)
            .filter(RoadmapItem.mini_roadmap_id == mini_roadmap_id)
            .order_by(RoadmapItem.order_in_mini.asc())
            .all()
        )
        roadmap_item = items[min(step_index, len(items) - 1)]
        state.step_index = step_index
        question = (
            db.query(AiQuestion)
            .filter(AiQuestion.roadmap_item_id == roadmap_item.id)
            .order_by(AiQuestion.created_at.asc())
            .first()
        )
        if not question:
            raise ValueError("Question not prepared for this mini roadmap")

        hint = question.hint if state.consecutive_failures >= 2 else None
        explanation = question.explanation if state.consecutive_failures >= 3 else None
        state.last_question_id = question.id
        state.updated_at = datetime.utcnow()
        db.commit()
        return _serialize_ai_question(question, hint, explanation)

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
