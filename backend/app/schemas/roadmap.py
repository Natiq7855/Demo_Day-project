from pydantic import BaseModel, Field


class PdfSelection(BaseModel):
    pdf_id: int
    page_start: int | None = None
    page_end: int | None = None


class RoadmapGenerateRequest(BaseModel):
    pdf_id: int | None = Field(default=None)
    pdf_ids: list[int] | None = Field(default=None)
    pdf_selections: list[PdfSelection] | None = None
    title: str
    chapter: str | None = None
    page_start: int | None = None
    page_end: int | None = None


class NextQuestionRequest(BaseModel):
    mini_roadmap_id: int
    roadmap_item_id: int | None = None
