import aiosqlite
from loguru import logger

from app.agents.news_collector.state import NewsCollectorState
from app.config import config
from app.utils.text_utils import compute_content_hash, title_similarity


async def deduplicate_news(state: NewsCollectorState) -> dict:
    """对采集的新闻进行去重：内容相似度去重 + 数据库已有条目去重"""
    raw_news = state.get("raw_news", [])
    if not raw_news:
        logger.warning("No news to deduplicate")
        return {"deduplicated_news": []}

    threshold = 0.85  # 标题相似度阈值
    seen_hashes: set[str] = set()
    seen_titles: list[str] = []
    deduped: list[dict] = []

    for item in raw_news:
        title = item.get("title", "")
        content_hash = item.get("content_hash", compute_content_hash(f"{title}{item.get('url', '')}"))

        # 1. 同批次 hash 去重
        if content_hash in seen_hashes:
            continue
        seen_hashes.add(content_hash)

        # 2. 标题相似度去重
        is_dup = False
        for prev_title in seen_titles:
            if title_similarity(title, prev_title) > threshold:
                is_dup = True
                logger.debug(f"Dup by similarity: '{title}' ≈ '{prev_title}'")
                break

        if is_dup:
            continue
        seen_titles.append(title)

        # 3. 数据库去重检查
        if await _exists_in_db(item):
            logger.debug(f"Dup by DB: {title}")
            continue

        deduped.append(item)

    logger.info(f"Deduplicated: {len(raw_news)} → {len(deduped)} items")
    return {"deduplicated_news": deduped}


async def _exists_in_db(item: dict) -> bool:
    try:
        db = await aiosqlite.connect(config.database_path)
        cursor = await db.execute("SELECT id FROM news WHERE url = ? OR content_hash = ?", (item.get("url", ""), item.get("content_hash", "")))
        row = await cursor.fetchone()
        await db.close()
        return row is not None
    except Exception:
        return False
