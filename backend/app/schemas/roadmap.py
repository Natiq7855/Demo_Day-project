from pydantic import BaseModel


class RoadmapQuestionCreate(BaseModel):
    question_text: str | None = None
    media_type: str | None = None
    media_path: str | None = None
    choices: list[str]
    answer_key: str


class MiniRoadmapCreate(BaseModel):
    title: str
    questions: list[RoadmapQuestionCreate]


class RoadmapCreateRequest(BaseModel):
    title: str
    minis: list[MiniRoadmapCreate]


class NextQuestionRequest(BaseModel):
    mini_roadmap_id: int
