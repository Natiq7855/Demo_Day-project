from pydantic import BaseModel


class RoadmapAssignRequest(BaseModel):
    roadmap_id: int
    target_type: str
    target_id: int


class PracticeExamAssignRequest(BaseModel):
    practice_exam_id: int
    target_type: str
    target_id: int


class PracticeExamUnassignRequest(BaseModel):
    practice_exam_id: int
    target_type: str
    target_id: int
