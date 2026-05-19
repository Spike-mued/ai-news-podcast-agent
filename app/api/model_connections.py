from __future__ import annotations


import aiosqlite
from fastapi import APIRouter, HTTPException

from app.config import config
from app.core.database import get_db
from app.models.model_connection import (
    ModelConnection,
    ModelConnectionList,
    ModelConnectionRequest,
    SUPPORTED_SERVICES,
)

router = APIRouter(prefix="/api/model-connections", tags=["model-connections"])


def _mask_key(key: str) -> str:
    if not key or len(key) < 12:
        return key
    return key[:8] + "****" + key[-4:]


def _row_to_model(row: aiosqlite.Row | dict) -> ModelConnection:
    d = dict(row)
    if d.get("api_key"):
        d["api_key"] = _mask_key(d["api_key"])
    return ModelConnection(**d)


@router.get("")
async def list_connections():
    db = await get_db()
    cursor = await db.execute("SELECT * FROM model_connections ORDER BY service_type, is_active DESC, created_at DESC")
    rows = await cursor.fetchall()
    items = [_row_to_model(r) for r in rows]

    active_llm = next((i for i in items if i.service_type == "llm" and i.is_active), None)
    active_tts = next((i for i in items if i.service_type == "tts" and i.is_active), None)

    await db.close()
    return ModelConnectionList(items=items, active_llm=active_llm, active_tts=active_tts).model_dump()


@router.get("/supported")
async def get_supported_services():
    return SUPPORTED_SERVICES


@router.post("")
async def create_connection(req: ModelConnectionRequest):
    db = await get_db()

    # 如果设为 active，先取消同类型的其他 active
    if req.is_active:
        await db.execute("UPDATE model_connections SET is_active = 0 WHERE service_type = ?", (req.service_type,))

    cursor = await db.execute(
        """INSERT INTO model_connections (name, service_type, provider, base_url, api_key, model, voice, extra_config, is_active)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (req.name, req.service_type, req.provider, req.base_url, req.api_key, req.model, req.voice, req.extra_config, 1 if req.is_active else 0),
    )
    await db.commit()
    new_id = cursor.lastrowid

    cursor = await db.execute("SELECT * FROM model_connections WHERE id = ?", (new_id,))
    row = await cursor.fetchone()
    await db.close()
    return _row_to_model(row).model_dump()


@router.put("/{conn_id}")
async def update_connection(conn_id: int, req: ModelConnectionRequest):
    db = await get_db()
    cursor = await db.execute("SELECT * FROM model_connections WHERE id = ?", (conn_id,))
    existing = await cursor.fetchone()
    if not existing:
        await db.close()
        raise HTTPException(status_code=404, detail="Connection not found")

    if req.is_active:
        await db.execute("UPDATE model_connections SET is_active = 0 WHERE service_type = ?", (req.service_type,))

    await db.execute(
        """UPDATE model_connections SET name=?, service_type=?, provider=?, base_url=?, api_key=?,
           model=?, voice=?, extra_config=?, is_active=? WHERE id=?""",
        (req.name, req.service_type, req.provider, req.base_url, req.api_key, req.model, req.voice, req.extra_config, 1 if req.is_active else 0, conn_id),
    )
    await db.commit()

    cursor = await db.execute("SELECT * FROM model_connections WHERE id = ?", (conn_id,))
    row = await cursor.fetchone()
    await db.close()
    return _row_to_model(row).model_dump()


@router.delete("/{conn_id}")
async def delete_connection(conn_id: int):
    db = await get_db()
    await db.execute("DELETE FROM model_connections WHERE id = ?", (conn_id,))
    await db.commit()
    await db.close()
    return {"ok": True}


@router.post("/{conn_id}/activate")
async def activate_connection(conn_id: int):
    db = await get_db()
    cursor = await db.execute("SELECT * FROM model_connections WHERE id = ?", (conn_id,))
    row = await cursor.fetchone()
    if not row:
        await db.close()
        raise HTTPException(status_code=404, detail="Connection not found")

    svc = row["service_type"]
    await db.execute("UPDATE model_connections SET is_active = 0 WHERE service_type = ?", (svc,))
    await db.execute("UPDATE model_connections SET is_active = 1 WHERE id = ?", (conn_id,))
    await db.commit()

    cursor = await db.execute("SELECT * FROM model_connections WHERE id = ?", (conn_id,))
    row = await cursor.fetchone()
    await db.close()
    return _row_to_model(row).model_dump()


@router.get("/active")
async def get_active_connections():
    """LLM/管道在执行时通过此接口获取当前激活的连接配置"""
    db = await get_db()
    cursor = await db.execute("SELECT * FROM model_connections WHERE is_active = 1")
    rows = await cursor.fetchall()
    await db.close()

    llm = next((dict(r) for r in rows if r["service_type"] == "llm"), None)
    tts = next((dict(r) for r in rows if r["service_type"] == "tts"), None)

    # Fallback to .env defaults
    if not llm:
        llm = {
            "name": "默认 LLM (.env)",
            "service_type": "llm",
            "provider": "dashscope",
            "base_url": config.dashscope_api_base,
            "api_key": config.dashscope_api_key,
            "model": config.dashscope_model,
            "is_active": False,
        }
    if not tts:
        tts = {
            "name": "默认 TTS (.env)",
            "service_type": "tts",
            "provider": "edge_tts",
            "base_url": "",
            "api_key": "",
            "model": "",
            "voice": config.tts_voice_zh,
            "is_active": False,
        }

    return {"llm": llm, "tts": tts}
