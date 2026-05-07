from __future__ import annotations

from pydantic import BaseModel, Field


class NewsItem(BaseModel):
    id: int | None = None
    title: str
    summary: str = ""
    url: str
    source: str
    source_type: str = "rss"
    published_at: str | None = None
    importance_score: int = 0
    importance_reason: str = ""
    content_hash: str = ""
    language: str = "zh"
    collected_at: str | None = None
    is_used: bool = False


class NewsListResponse(BaseModel):
    total: int
    items: list[NewsItem]
    page: int = 1
    page_size: int = 20


class NewsStats(BaseModel):
    total_news: int
    today_news: int
    avg_score: float
    by_source: dict[str, int]
    by_language: dict[str, int]
