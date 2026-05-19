from __future__ import annotations

from pydantic import BaseModel


class PlaylistItem(BaseModel):
    id: int | None = None
    name: str
    podcast_ids: list[int] = []
    audio_path: str | None = None
    total_duration: float = 0.0
    status: str = "building"
    created_at: str | None = None
    completed_at: str | None = None


class PlaylistListResponse(BaseModel):
    total: int
    items: list[PlaylistItem]
