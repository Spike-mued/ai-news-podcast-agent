import json

import aiosqlite
from loguru import logger

from app.agents.news_collector.state import NewsCollectorState
from app.config import config
from app.core.llm_factory import llm_factory


RANKING_PROMPT = """You are an AI news editor. Rate the following AI/tech news items by importance on a scale of 1-10.

Scoring criteria:
- Technical Breakthrough (3 pts): Does it represent a significant technical advancement?
- Industry Impact (3 pts): How much does it affect the AI industry?
- Reader Interest (2 pts): Would AI practitioners care about this?
- Timeliness (2 pts): Is this breaking or time-sensitive news?

Return a JSON array with objects containing:
- "url": the original URL
- "score": integer 1-10
- "reason": one-line explanation in Chinese (中文)

News items:
{news_json}

Return ONLY the JSON array, no other text."""


async def rank_news(state: NewsCollectorState) -> dict:
    """快速评分：关键词+来源优先级，可选 LLM 重排"""
    deduped = state.get("deduplicated_news", [])
    max_items = state.get("max_items", config.news_max_items)

    if not deduped:
        logger.warning("No news to rank")
        return {"ranked_news": [], "final_news": [], "pipeline_status": "completed"}

    # Step 1: 快速预排序（关键词 + 来源优先级）
    keywords = _get_keywords()
    for item in deduped:
        title = item.get("title", "").lower()
        summary = item.get("summary", "").lower()
        text = title + " " + summary
        kw_match = sum(1 for kw in keywords if kw.lower() in text) if keywords else 0
        base_score = min(9, 4 + item.get("priority_weight", 5) // 2 + kw_match)
        item["importance_score"] = base_score
        item["importance_reason"] = f"快速评分 (匹配{kw_match}关键词, 优先级{item.get('priority_weight',5)})"

    # Step 2: 预排序取 Top N
    deduped.sort(key=lambda x: x.get("importance_score", 0), reverse=True)
    top_n = min(len(deduped), max(40, max_items * 2))
    candidates = deduped[:top_n]

    # Step 3: LLM 精排 Top 20（单批次快速完成）
    llm_batch = candidates[:20]
    try:
        llm = llm_factory.create_chat_model(temperature=0.3, streaming=False, timeout=30)
        news_for_llm = [{"title": n["title"][:80], "url": n["url"], "source": n["source"]} for n in llm_batch]
        news_json = json.dumps(news_for_llm, ensure_ascii=False)
        response = await llm.ainvoke(RANKING_PROMPT.format(news_json=news_json))
        content = response.content if hasattr(response, "content") else str(response)
        content = _extract_json(content)
        scores = json.loads(content)
        score_map = {s["url"]: (s.get("score", 5), s.get("reason", "")) for s in scores}
        for item in llm_batch:
            score, reason = score_map.get(item["url"], (item.get("importance_score", 5), ""))
            item["importance_score"] = score
            item["importance_reason"] = reason
    except Exception as e:
        logger.warning(f"LLM ranking failed, using heuristic scores: {e}")
        # 快速评分已经完成，继续使用启发式分数

    # 按分数降序排序
    candidates.sort(key=lambda x: x.get("importance_score", 0), reverse=True)

    # 关键词模式下过滤低相关度新闻
    if config.news_keywords_mode == "include" and keywords:
        candidates = [n for n in candidates if n.get("importance_score", 0) >= 6]

    # 截取 Top N
    all_ranked = candidates
    final_news = candidates[:max_items]

    # 保存到数据库
    await _save_to_db(final_news)

    logger.info(f"Ranked: {len(deduped)} → {len(final_news)} items (top {max_items})")
    return {"ranked_news": all_ranked, "final_news": final_news, "pipeline_status": "completed"}


def _get_keywords() -> list[str]:
    """解析关键词配置"""
    raw = config.news_keywords.strip()
    if not raw:
        return []
    return [k.strip().lower() for k in raw.split(",") if k.strip()]


def _extract_json(text: str) -> str:
    """从 LLM 回复中提取 JSON"""
    text = text.strip()
    if "```json" in text:
        start = text.index("```json") + 7
        end = text.index("```", start)
        return text[start:end].strip()
    elif "```" in text:
        start = text.index("```") + 3
        end = text.index("```", start)
        return text[start:end].strip()
    if text.startswith("["):
        return text
    return text


async def _save_to_db(news_items: list[dict]):
    try:
        db = await aiosqlite.connect(config.database_path)
        for item in news_items:
            await db.execute(
                """INSERT OR IGNORE INTO news
                   (title, summary, url, source, source_type, published_at,
                    importance_score, importance_reason, content_hash, language, raw_data, collected_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))""",
                (
                    item.get("title", ""),
                    item.get("summary", ""),
                    item.get("url", ""),
                    item.get("source", ""),
                    item.get("source_type", "rss"),
                    item.get("published_at", ""),
                    item.get("importance_score", 0),
                    item.get("importance_reason", ""),
                    item.get("content_hash", ""),
                    item.get("language", "zh"),
                    item.get("raw_data", ""),
                ),
            )
        await db.commit()
        await db.close()
        logger.debug(f"Saved {len(news_items)} news items to DB")
    except Exception as e:
        logger.error(f"Failed to save news to DB: {e}")
