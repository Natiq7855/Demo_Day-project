from pydantic import BaseModel


class SubmitAttemptRequest(BaseModel):
    roadmap_item_id: int
    question_id: int
    is_correct: bool
