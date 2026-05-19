from __future__ import annotations

import os

import aiosqlite
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.config import config
from app.models.podcast import CurrentPlayback, PodcastItem, PodcastListResponse
from app.models.request import PipelineTriggerRequest
from app.services.pipeline_service import run_full_pipeline
from app.services.stream_service import stream_service

router = APIRouter(tags=["podcast"])


@router.get("/api/podcasts", response_model=PodcastListResponse)
async def list_podcasts(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    db = await aiosqlite.connect(config.database_path)
    db.row_factory = aiosqlite.Row

    cursor = await db.execute("SELECT COUNT(*) FROM podcasts WHERE is_archived = 0")
    total = (await cursor.fetchone())[0]

    offset = (page - 1) * page_size
    cursor = await db.execute(
        "SELECT * FROM podcasts WHERE is_archived = 0 ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (page_size, offset),
    )
    rows = await cursor.fetchall()
    await db.close()

    items = [PodcastItem(**dict(row)) for row in rows]
    return PodcastListResponse(total=total, items=items, page=page, page_size=page_size)


@router.get("/api/podcasts/current", response_model=CurrentPlayback)
async def get_current_playback():
    status = stream_service.get_status()
    current_metadata = status.get("current_metadata", {})

    podcast = None
    if current_metadata:
        podcast = PodcastItem(**current_metadata.get("podcast", {}))

    return CurrentPlayback(
        podcast=podcast,
        playlist_name=status.get("current_file", ""),
        position_seconds=status.get("position_bytes", 0) / (128 * 1024 / 8) if status.get("position_bytes") else 0,
        queue_length=status.get("queue_length", 0),
        status="playing" if status.get("is_active") else "idle",
    )


@router.get("/api/podcasts/{podcast_id}/audio")
async def download_podcast_audio(podcast_id: int):
    db = await aiosqlite.connect(config.database_path)
    db.row_factory = aiosqlite.Row
    cursor = await db.execute("SELECT * FROM podcasts WHERE id = ?", (podcast_id,))
    row = await cursor.fetchone()
    await db.close()

    if not row:
        raise HTTPException(status_code=404, detail="Podcast not found")

    audio_path = row["audio_path"]
    if not audio_path or not os.path.exists(audio_path):
        raise HTTPException(status_code=404, detail="Audio file not found")

    return FileResponse(audio_path, media_type="audio/mpeg", filename=os.path.basename(audio_path))


@router.post("/api/pipeline/trigger")
async def trigger_pipeline(request: PipelineTriggerRequest | None = None):
    if request is None:
        request = PipelineTriggerRequest()

    result = await run_full_pipeline(
        sources=request.sources if request.sources else None,
        max_items=request.max_items if request.max_items > 0 else None,
        force=request.force,
    )
    return result
