import json

from sqlalchemy.orm import Session

from app.db.models import Roadmap, RoadmapItem
from app.services.groq_client import create_json_completion
from app.utils.json_schema import ROADMAP_SCHEMA


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
            "content": "Return only JSON matching the provided schema for a roadmap.",
        },
        {
            "role": "user",
            "content": (
                "Analyze the context and generate a sequential roadmap with question types.\n"
                f"Title: {title}\nContext: {chunk_context}"
            ),
        },
    ]
    content = create_json_completion(messages, ROADMAP_SCHEMA)
    payload = json.loads(content)

    roadmap = Roadmap(
        title=title,
        pdf_id=pdf_id,
        created_by=created_by,
        page_start=page_start,
        page_end=page_end,
    )
    db.add(roadmap)
    db.flush()

    for index, item in enumerate(payload["items"], start=1):
        db.add(
            RoadmapItem(
                roadmap_id=roadmap.id,
                topic=item["topic"],
                question_type=item["question_type"],
                difficulty=item["difficulty"],
                sequence_index=index,
                metadata=item.get("metadata"),
            )
        )

    db.commit()
    return roadmap.id
