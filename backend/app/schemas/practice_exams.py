from pydantic import BaseModel


class PracticeExamSubmitRequest(BaseModel):
    practice_exam_id: int
    score: int
