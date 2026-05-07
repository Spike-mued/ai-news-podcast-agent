import aiosqlite
from fastapi import APIRouter, HTTPException, Query

from app.config import config
from app.models.news import NewsItem, NewsListResponse, NewsStats

router = APIRouter(tags=["news"])


@router.get("/api/news", response_model=NewsListResponse)
async def list_news(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    source: str = Query(default=""),
    min_score: int = Query(default=0, ge=0, le=10),
    language: str = Query(default=""),
):
    db = await aiosqlite.connect(config.database_path)
    db.row_factory = aiosqlite.Row

    conditions = []
    params: list = []

    if source:
        conditions.append("source = ?")
        params.append(source)
    if min_score > 0:
        conditions.append("importance_score >= ?")
        params.append(min_score)
    if language:
        conditions.append("language = ?")
        params.append(language)

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

    cursor = await db.execute(f"SELECT COUNT(*) FROM news{where_clause}", params)
    total = (await cursor.fetchone())[0]

    offset = (page - 1) * page_size
    cursor = await db.execute(
        f"SELECT * FROM news{where_clause} ORDER BY importance_score DESC, collected_at DESC LIMIT ? OFFSET ?",
        params + [page_size, offset],
    )
    rows = await cursor.fetchall()
    await db.close()

    items = [NewsItem(**dict(row)) for row in rows]
    return NewsListResponse(total=total, items=items, page=page, page_size=page_size)


@router.get("/api/news/stats", response_model=NewsStats)
async def get_news_stats():
    db = await aiosqlite.connect(config.database_path)
    db.row_factory = aiosqlite.Row

    cursor = await db.execute("SELECT COUNT(*) FROM news")
    total = (await cursor.fetchone())[0]

    cursor = await db.execute("SELECT COUNT(*) FROM news WHERE date(collected_at) = date('now', 'localtime')")
    today = (await cursor.fetchone())[0]

    cursor = await db.execute("SELECT AVG(importance_score) FROM news")
    avg = (await cursor.fetchone())[0] or 0

    cursor = await db.execute("SELECT source, COUNT(*) as cnt FROM news GROUP BY source")
    by_source = {row["source"]: row["cnt"] for row in await cursor.fetchall()}

    cursor = await db.execute("SELECT language, COUNT(*) as cnt FROM news GROUP BY language")
    by_language = {row["language"]: row["cnt"] for row in await cursor.fetchall()}

    await db.close()
    return NewsStats(total_news=total, today_news=today, avg_score=avg, by_source=by_source, by_language=by_language)
