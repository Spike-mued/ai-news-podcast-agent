from __future__ import annotations

import aiosqlite
from fastapi import APIRouter
from loguru import logger

from app.config import config

router = APIRouter(prefix="/api/archive", tags=["archive"])


@router.post("/news")
async def archive_old_news(days: int = 1):
    """归档 N 天前的新闻 — 默认归档昨天及之前的"""
    db = await aiosqlite.connect(config.database_path)
    await db.execute(
        "UPDATE news SET is_archived = 1 WHERE is_archived = 0 AND date(collected_at) < date('now', 'localtime', ?)",
        (f"-{days} days",),
    )
    await db.commit()

    cursor = await db.execute("SELECT changes()")
    count = (await cursor.fetchone())[0]
    await db.close()
    logger.info(f"Archived {count} old news items (>{days} day(s) ago)")
    return {"ok": True, "archived_count": count, "type": "news"}


@router.post("/podcasts")
async def archive_played_podcasts():
    """归档已入队播放的播客（关联的新闻 is_used=1 且播客 status='completed'）"""
    db = await aiosqlite.connect(config.database_path)
    # 归档 24 小时前完成的、且关联新闻已使用的播客
    await db.execute(
        """UPDATE podcasts SET is_archived = 1
           WHERE is_archived = 0 AND status = 'completed'
           AND datetime(completed_at) < datetime('now', 'localtime', '-1 hours')"""
    )
    await db.commit()

    cursor = await db.execute("SELECT changes()")
    count = (await cursor.fetchone())[0]
    await db.close()
    logger.info(f"Archived {count} played podcasts")
    return {"ok": True, "archived_count": count, "type": "podcasts"}


@router.post("/all")
async def archive_all():
    """一键归档旧新闻和已播播客"""
    news_result = await archive_old_news()
    podcast_result = await archive_played_podcasts()
    total = news_result["archived_count"] + podcast_result["archived_count"]
    logger.info(f"Archive all: {total} items ({news_result['archived_count']} news, {podcast_result['archived_count']} podcasts)")
    return {"ok": True, "news_archived": news_result["archived_count"], "podcasts_archived": podcast_result["archived_count"], "total": total}


@router.get("/status")
async def archive_status():
    """查看活跃 vs 归档数据统计"""
    db = await aiosqlite.connect(config.database_path)
    db.row_factory = aiosqlite.Row

    cursor = await db.execute("SELECT COUNT(*) AS cnt, is_archived FROM news GROUP BY is_archived")
    news = {("archived" if r["is_archived"] else "active"): r["cnt"] for r in await cursor.fetchall()}

    cursor = await db.execute("SELECT COUNT(*) AS cnt, is_archived FROM podcasts GROUP BY is_archived")
    podcasts = {("archived" if r["is_archived"] else "active"): r["cnt"] for r in await cursor.fetchall()}

    await db.close()
    return {"news": news, "podcasts": podcasts}
