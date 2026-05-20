from pydantic import BaseModel


class PracticeExamSubmitRequest(BaseModel):
    practice_exam_id: int
    answers: list[str]
    score: int | None = None
