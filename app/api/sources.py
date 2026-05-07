from __future__ import annotations

import aiosqlite
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import config

router = APIRouter(tags=["sources"])


class SourceCreate(BaseModel):
    name: str
    type: str = "rss"
    url: str
    language: str = "zh"
    priority: int = 5
    is_enabled: bool = True
    keywords: str = ""


class SourceUpdate(BaseModel):
    type: str | None = None
    url: str | None = None
    language: str | None = None
    priority: int | None = None
    is_enabled: bool | None = None
    keywords: str | None = None


@router.get("/api/sources")
async def list_sources():
    db = await aiosqlite.connect(config.database_path)
    db.row_factory = aiosqlite.Row
    cursor = await db.execute("SELECT * FROM news_sources ORDER BY priority DESC")
    rows = await cursor.fetchall()
    await db.close()
    return {"total": len(rows), "items": [dict(r) for r in rows]}


@router.post("/api/sources")
async def add_source(source: SourceCreate):
    db = await aiosqlite.connect(config.database_path)
    try:
        cursor = await db.execute(
            "INSERT INTO news_sources (name, type, url, language, priority, is_enabled, keywords) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (source.name, source.type, source.url, source.language, source.priority, int(source.is_enabled), source.keywords),
        )
        await db.commit()
        sid = cursor.lastrowid
        await db.close()
        return {"id": sid, "name": source.name, "status": "created"}
    except aiosqlite.IntegrityError:
        await db.close()
        raise HTTPException(status_code=409, detail=f"Source '{source.name}' already exists")


@router.put("/api/sources/{name}")
async def update_source(name: str, update: SourceUpdate):
    db = await aiosqlite.connect(config.database_path)
    updates = []
    params: list = []
    for field in ["type", "url", "language", "priority", "keywords"]:
        val = getattr(update, field, None)
        if val is not None:
            updates.append(f"{field} = ?")
            params.append(val)
    if update.is_enabled is not None:
        updates.append("is_enabled = ?")
        params.append(int(update.is_enabled))
    if not updates:
        await db.close()
        return {"status": "no changes"}
    params.append(name)
    cursor = await db.execute(f"UPDATE news_sources SET {', '.join(updates)} WHERE name = ?", params)
    await db.commit()
    if cursor.rowcount == 0:
        await db.close()
        raise HTTPException(status_code=404, detail=f"Source '{name}' not found")
    await db.close()
    return {"status": "updated", "name": name}


@router.delete("/api/sources/{name}")
async def delete_source(name: str):
    db = await aiosqlite.connect(config.database_path)
    cursor = await db.execute("DELETE FROM news_sources WHERE name = ?", (name,))
    await db.commit()
    if cursor.rowcount == 0:
        await db.close()
        raise HTTPException(status_code=404, detail=f"Source '{name}' not found")
    await db.close()
    return {"status": "deleted", "name": name}


@router.post("/api/sources/reload")
async def reload_sources():
    from app.sources.source_registry import reload_registry
    await reload_registry()
    return {"status": "reloaded"}
