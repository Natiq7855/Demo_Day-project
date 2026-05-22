import json

from sqlalchemy.orm import Session

from app.db.models import AiQuestion, Roadmap, RoadmapItem
from app.services.gemini_client import create_json_completion
from app.utils.json_schema import ROADMAP_SCHEMA


REQUIRED_QUESTION_TYPES = [
    "multiple_choice",
    "true_false",
    "short_answer",
    "problem_solving",
    "concept_explanation",
]


def _parse_json_payload(content: str) -> dict:
    text = content.strip()
    if text.startswith("```"):
        text = text.removeprefix("```json").removeprefix("```").strip()
        if "```" in text:
            text = text.split("```", 1)[0].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"Gemini returned invalid JSON: {error}") from error


def _extract_items(payload: dict) -> list[dict]:
    if isinstance(payload.get("items"), list):
        return payload["items"]

    for key in ("roadmap", "roadmap_items", "topics", "lessons"):
        value = payload.get(key)
        if isinstance(value, list):
            return value

    if isinstance(payload.get("roadmap"), dict) and isinstance(payload["roadmap"].get("items"), list):
        return payload["roadmap"]["items"]

    raise ValueError(f"Gemini returned roadmap JSON without an items list. Keys: {', '.join(payload.keys())}")


def generate_roadmap(
    db: Session,
    pdf_id: int,
    title: str,
    chunk_context: str,
    created_by: int,
    page_start: int | None,
    page_end: int | None,
):
    messages = [
        {
            "role": "system",
            "content": (
                "Return only a JSON object with this exact top-level shape: "
                '{"items":[{"topic":"...","question_type":"multiple_choice","difficulty":"easy|medium|hard",'
                '"question_text":"...","choices":["..."],"answer_key":["..."],"hint":"...",'
                '"explanation":"...","metadata":null}]}. Do not wrap it in another key. '
                "Every item must include a ready-to-show student question created from the PDF context."
            ),
        },
        {
            "role": "user",
            "content": (
                "Analyze the context and generate a teacher-created roadmap question set. "
                "Create at least one question for every required question type, using the same topic/content style "
                "as the PDF. Required question types: "
                f"{', '.join(REQUIRED_QUESTION_TYPES)}.\n"
                f"Title: {title}\nContext: {chunk_context}"
            ),
        },
    ]
    content = create_json_completion(messages, ROADMAP_SCHEMA)
    payload = _parse_json_payload(content)
    items = _extract_items(payload)
    if not items:
        raise ValueError("Gemini returned an empty roadmap.")

    roadmap = Roadmap(
        title=title,
        pdf_id=pdf_id,
        created_by=created_by,
        page_start=page_start,
        page_end=page_end,
    )
    db.add(roadmap)
    db.flush()

    seen_types = {item.get("question_type") for item in items}
    for question_type in REQUIRED_QUESTION_TYPES:
        if question_type not in seen_types:
            items.append(
                {
                    "topic": title,
                    "question_type": question_type,
                    "difficulty": "medium",
                    "question_text": f"Create a {question_type.replace('_', ' ')} response about {title}.",
                    "choices": None,
                    "answer_key": None,
                    "hint": "Use the assigned PDF material.",
                    "explanation": "This fallback question was added to ensure every required type is present.",
                    "metadata": {"fallback": True},
                }
            )

    for index, item in enumerate(items, start=1):
        roadmap_item = RoadmapItem(
            roadmap_id=roadmap.id,
            topic=item.get("topic") or item.get("title") or f"Topic {index}",
            question_type=item.get("question_type") or item.get("type") or "conceptual",
            difficulty=item.get("difficulty") or "medium",
            sequence_index=index,
            metadata_=item.get("metadata"),
        )
        db.add(roadmap_item)
        db.flush()

        db.add(
            AiQuestion(
                roadmap_item_id=roadmap_item.id,
                student_id=created_by,
                type_label=roadmap_item.question_type,
                difficulty=roadmap_item.difficulty,
                question_text=item.get("question_text") or f"What should a student know about {roadmap_item.topic}?",
                choices=item.get("choices"),
                answer_key=item.get("answer_key"),
                explanation=item.get("explanation"),
                hint=item.get("hint"),
                source="teacher_gemini",
            )
        )

    db.commit()
    return roadmap.id
