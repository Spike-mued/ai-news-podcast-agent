from pydantic import BaseModel, Field


class PipelineTriggerRequest(BaseModel):
    sources: list[str] = []
    max_items: int = 0
    force: bool = False


class PaginationRequest(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
