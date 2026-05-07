from datetime import datetime

from langchain.tools import tool
from loguru import logger

from app.config import config


@tool
async def get_current_time(timezone: str = "Asia/Shanghai") -> str:
    """获取当前时间，用于新闻采集时间标记"""
    try:
        from zoneinfo import ZoneInfo

        tz = ZoneInfo(timezone)
        now = datetime.now(tz)
        return now.strftime("%Y-%m-%d %H:%M:%S %Z")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@tool
async def search_news_headlines(query: str, max_results: int = 10) -> str:
    """搜索最近的AI新闻头条（通过已采集的数据库查询）"""
    import aiosqlite

    try:
        db = await aiosqlite.connect(config.database_path)
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT title, source, importance_score, collected_at FROM news "
            "WHERE title LIKE ? OR summary LIKE ? "
            "ORDER BY importance_score DESC, collected_at DESC LIMIT ?",
            (f"%{query}%", f"%{query}%", max_results),
        )
        rows = await cursor.fetchall()
        await db.close()

        if not rows:
            return f"No news found for query: {query}"

        results = [f"- [{r['importance_score']}] {r['title']} ({r['source']})" for r in rows]
        return "\n".join(results)
    except Exception as e:
        logger.error(f"search_news_headlines failed: {e}")
        return f"Error: {e}"


@tool
async def get_news_stats() -> str:
    """获取新闻采集统计数据"""
    import aiosqlite

    try:
        db = await aiosqlite.connect(config.database_path)
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("SELECT COUNT(*) as total FROM news")
        total = (await cursor.fetchone())["total"]

        cursor = await db.execute(
            "SELECT COUNT(*) as today FROM news WHERE date(collected_at) = date('now', 'localtime')"
        )
        today = (await cursor.fetchone())["today"]

        cursor = await db.execute("SELECT AVG(importance_score) as avg FROM news")
        avg = (await cursor.fetchone())["avg"] or 0

        await db.close()
        return f"Total news: {total}, Today: {today}, Avg score: {avg:.1f}"
    except Exception as e:
        return f"Error: {e}"
