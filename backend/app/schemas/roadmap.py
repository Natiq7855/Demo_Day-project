from pydantic import BaseModel


class RoadmapGenerateRequest(BaseModel):
    pdf_id: int
    title: str
    chapter: str | None = None
    page_start: int | None = None
    page_end: int | None = None


class NextQuestionRequest(BaseModel):
    roadmap_item_id: int
