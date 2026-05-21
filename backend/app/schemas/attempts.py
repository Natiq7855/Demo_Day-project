from pydantic import BaseModel


class SubmitAttemptRequest(BaseModel):
    roadmap_item_id: int | None = None
    mini_roadmap_id: int | None = None
    question_id: int
    is_correct: bool | None = None
    selected_answer: str | None = None
