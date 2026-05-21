from pydantic import BaseModel


class SubmitAttemptRequest(BaseModel):
    mini_roadmap_id: int | None = None
    roadmap_item_id: int
    selected_answer: str
