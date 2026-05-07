from __future__ import annotations

from pydantic import BaseModel, Field


class PodcastItem(BaseModel):
    id: int | None = None
    news_id: int
    title: str
    script: str = ""
    audio_path: str | None = None
    audio_duration: float = 0.0
    importance_level: int = 5
    status: str = "pending"
    error_message: str | None = None
    created_at: str | None = None
    completed_at: str | None = None


class PodcastListResponse(BaseModel):
    total: int
    items: list[PodcastItem]
    page: int = 1
    page_size: int = 20


class CurrentPlayback(BaseModel):
    podcast: PodcastItem | None = None
    playlist_name: str = ""
    position_seconds: float = 0.0
    queue_length: int = 0
    status: str = "idle"
