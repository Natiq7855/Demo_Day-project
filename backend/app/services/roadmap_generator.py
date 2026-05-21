import json

from sqlalchemy.orm import Session

from app.db.models import AiQuestion, Roadmap, RoadmapItem, RoadmapMini, RoadmapSourcePdf
from app.services.groq_client import create_json_completion
from app.utils.json_schema import ROADMAP_SCHEMA


REQUIRED_QUESTION_TYPES = [
    "definition",
    "concept_check",
    "application",
    "analysis",
]


def _extract_items(payload: dict) -> list[dict]:
    if isinstance(payload.get("items"), list):
        return payload["items"]

    for key in ("roadmap", "roadmap_items", "topics", "lessons"):
        value = payload.get(key)
        if isinstance(value, list):
            return value

    if isinstance(payload.get("roadmap"), dict) and isinstance(payload["roadmap"].get("items"), list):
        return payload["roadmap"]["items"]

    raise ValueError(f"Groq returned roadmap JSON without an items list. Keys: {', '.join(payload.keys())}")


def _extract_mini_roadmaps(payload: dict) -> list[dict]:
    if isinstance(payload.get("mini_roadmaps"), list):
        return payload["mini_roadmaps"]
    for key in ("miniRoadmaps", "miniRoadmap", "groups"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return []


def _extract_questions(payload: dict) -> list[dict]:
    if isinstance(payload.get("questions"), list):
        return payload["questions"]
    return []


def _normalize_choice_list(options: list) -> list[str]:
    return [str(option).strip() for option in options if str(option).strip()]


def _coerce_mini_from_questions(title: str, questions: list[dict]) -> list[dict]:
    normalized = []
    for entry in questions:
        options = _normalize_choice_list(entry.get("options") or [])
        correct = str(entry.get("correct") or "").strip()
        if not options or not correct:
            continue
        normalized.append(
            {
                "topic": title,
                "difficulty": "medium",
                "question_text": entry.get("question") or "",
                "choices": options,
                "answer_key": [correct],
                "hint": entry.get("hint"),
                "explanation": entry.get("explanation"),
                "metadata": {
                    "source": "fallback_questions",
                    "source_snippet": entry.get("source_snippet") or "",
                },
            }
        )

    while len(normalized) < 4:
        normalized.append(
            {
                "topic": title,
                "difficulty": "medium",
                "question_text": f"Create a multiple choice question about {title}.",
                "choices": ["A", "B", "C", "D"],
                "answer_key": ["A"],
                "hint": "Use the assigned PDF material.",
                "explanation": "This fallback question was added to reach 4 questions.",
                "metadata": {"fallback": True, "source_snippet": ""},
            }
        )

    return [
        {
            "question_type": "multiple_choice",
            "questions": normalized[:4],
        }
    ]


def generate_roadmap(
    db: Session,
    pdf_ids: list[int],
    title: str,
    chunk_context: str,
    created_by: int,
    page_start: int | None,
    page_end: int | None,
    pdf_selections: list[dict] | None = None,
):
    messages = [
        {
            "role": "system",
            "content": (
                "You are an AI tutor. Return only a JSON object matching the provided schema. "
                "Every question must be multiple choice with 4 options and exactly one correct answer."
            ),
        },
        {
            "role": "user",
            "content": (
                "Analyze the context and build mini roadmaps for the teacher-selected topic. "
                "Each mini roadmap is grouped by a distinct question type you identify in the PDFs. "
                "Each mini roadmap must include exactly 4 multiple-choice questions of the SAME type. "
                "Prefer extracting questions from the PDFs. If there are not enough questions, create similar ones "
                "that stay grounded in the same PDF content. Use all PDFs when multiple sources are provided. "
                "The PDFs may not contain multiple-choice questions. Extract questions as it is but generate multiple choices for this question, "
                "then create 4 answer choices (one correct, three plausible distractors). "
                "Every question must reference the PDF content explicitly: add a short quote in metadata.source_snippet. "
                "Do not invent facts not present in the PDFs. "
                "Provide a short hint and explanation for every question so the app can reveal them later. "
                "Question types should be distinct and derived from the material.\n"
                f"Target topic: {title}\nContext: {chunk_context}\n"
                f"Suggested question type labels: {', '.join(REQUIRED_QUESTION_TYPES)}\n"
                "Return JSON with this shape: {\"mini_roadmaps\":[{\"question_type\":\"...\",\"questions\":[{\"topic\":\"...\",\"difficulty\":\"easy|medium|hard\",\"question_text\":\"...\",\"choices\":[\"A\",\"B\",\"C\",\"D\"],\"answer_key\":[\"A\"],\"hint\":\"...\",\"explanation\":\"...\"}]}]}"
            ),
        },
    ]
    content = create_json_completion(messages, ROADMAP_SCHEMA)
    payload = json.loads(content)
    mini_roadmaps = _extract_mini_roadmaps(payload)
    if not mini_roadmaps:
        questions = _extract_questions(payload)
        if questions:
            mini_roadmaps = _coerce_mini_from_questions(title, questions)
    items = _extract_items(payload) if not mini_roadmaps else []
    if not mini_roadmaps and not items:
        raise ValueError("Groq returned an empty roadmap.")

    primary_pdf_id = pdf_ids[0]
    roadmap = Roadmap(
        title=title,
        pdf_id=primary_pdf_id,
        created_by=created_by,
        page_start=page_start,
        page_end=page_end,
    )
    db.add(roadmap)
    db.flush()

    if pdf_selections:
        for selection in pdf_selections:
            db.add(
                RoadmapSourcePdf(
                    roadmap_id=roadmap.id,
                    pdf_id=selection["pdf_id"],
                    page_start=selection.get("page_start"),
                    page_end=selection.get("page_end"),
                )
            )
    else:
        for pdf_id in dict.fromkeys(pdf_ids):
            db.add(RoadmapSourcePdf(roadmap_id=roadmap.id, pdf_id=pdf_id))

    if mini_roadmaps:
        for mini_index, mini in enumerate(mini_roadmaps, start=1):
            question_type = mini.get("question_type") or "multiple_choice"
            roadmap_mini = RoadmapMini(
                roadmap_id=roadmap.id,
                question_type=question_type,
                sequence_index=mini_index,
            )
            db.add(roadmap_mini)
            db.flush()

            questions = mini.get("questions") or []
            if len(questions) < 4:
                raise ValueError("Each mini roadmap must include 4 questions.")

            for order_index, question in enumerate(questions[:4], start=1):
                roadmap_item = RoadmapItem(
                    roadmap_id=roadmap.id,
                    mini_roadmap_id=roadmap_mini.id,
                    topic=question.get("topic") or title,
                    question_type=question_type,
                    difficulty=question.get("difficulty") or "medium",
                    sequence_index=mini_index,
                    order_in_mini=order_index,
                    metadata_=question.get("metadata"),
                )
                db.add(roadmap_item)
                db.flush()

                db.add(
                    AiQuestion(
                        roadmap_item_id=roadmap_item.id,
                        student_id=created_by,
                        type_label=question_type,
                        difficulty=roadmap_item.difficulty,
                        question_text=question.get("question_text") or "",
                        choices=question.get("choices"),
                        answer_key=question.get("answer_key"),
                        explanation=question.get("explanation"),
                        hint=question.get("hint"),
                        source="ai_generated",
                    )
                )

        db.commit()
        return roadmap.id

    seen_types = {item.get("question_type") for item in items}
    for question_type in REQUIRED_QUESTION_TYPES:
        if question_type not in seen_types:
            items.append(
                {
                    "topic": title,
                    "question_type": question_type,
                    "difficulty": "medium",
                    "question_text": f"Create a multiple choice question about {title}.",
                    "choices": ["A", "B", "C", "D"],
                    "answer_key": ["A"],
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
                source="ai_generated",
            )
        )

    db.commit()
    return roadmap.id
