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
    """使用 LLM 对新闻进行重要性评分和排序"""
    deduped = state.get("deduplicated_news", [])
    max_items = state.get("max_items", config.news_max_items)

    if not deduped:
        logger.warning("No news to rank")
        return {"ranked_news": [], "final_news": [], "pipeline_status": "completed"}

    # 超过一定数量时分批评分
    batch_size = 10
    all_ranked: list[dict] = []

    for i in range(0, len(deduped), batch_size):
        batch = deduped[i : i + batch_size]

        # 构建简化的新闻列表给 LLM
        news_for_llm = [{"title": n["title"], "url": n["url"], "source": n["source"]} for n in batch]
        news_json = json.dumps(news_for_llm, ensure_ascii=False, indent=2)

        try:
            llm = llm_factory.create_chat_model(temperature=0.3, streaming=False)
            response = await llm.ainvoke(RANKING_PROMPT.format(news_json=news_json))
            content = response.content if hasattr(response, "content") else str(response)
            content = _extract_json(content)
            scores = json.loads(content)

            # 合并评分到新闻条目
            score_map = {s["url"]: (s.get("score", 5), s.get("reason", "")) for s in scores}

            for item in batch:
                score, reason = score_map.get(item["url"], (5, ""))
                if score < config.news_importance_threshold:
                    continue
                item["importance_score"] = score
                item["importance_reason"] = reason
                all_ranked.append(item)

        except Exception as e:
            logger.error(f"Ranking batch failed: {e}")
            for item in batch:
                item["importance_score"] = 5
                item["importance_reason"] = "Default score (ranking failed)"
                all_ranked.append(item)

    # 按分数降序排序
    all_ranked.sort(key=lambda x: x.get("importance_score", 0), reverse=True)

    # 截取 Top N
    final_news = all_ranked[:max_items]

    # 保存到数据库
    await _save_to_db(final_news)

    logger.info(f"Ranked: {len(deduped)} → {len(final_news)} items (top {max_items})")
    return {"ranked_news": all_ranked, "final_news": final_news, "pipeline_status": "completed"}


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
