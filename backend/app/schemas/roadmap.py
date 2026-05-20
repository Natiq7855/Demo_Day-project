from pydantic import BaseModel, Field


class RoadmapGenerateRequest(BaseModel):
    pdf_id: int | None = Field(default=None)
    pdf_ids: list[int] | None = Field(default=None)
    title: str
    chapter: str | None = None
    page_start: int | None = None
    page_end: int | None = None


class NextQuestionRequest(BaseModel):
    roadmap_item_id: int
