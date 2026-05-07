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

    # 关键词加分
    keywords = _get_keywords()
    if keywords:
        all_ranked = _boost_keywords(all_ranked, keywords)

    # 按分数降序排序
    all_ranked.sort(key=lambda x: x.get("importance_score", 0), reverse=True)

    # 关键词模式下过滤不匹配的新闻
    if config.news_keywords_mode == "include" and keywords:
        all_ranked = [n for n in all_ranked if n.get("_keyword_match", False) or n.get("importance_score", 0) >= 8]

    # 截取 Top N
    final_news = all_ranked[:max_items]

    # 保存到数据库
    await _save_to_db(final_news)

    logger.info(f"Ranked: {len(deduped)} → {len(final_news)} items (top {max_items}, keywords={keywords})")
    return {"ranked_news": all_ranked, "final_news": final_news, "pipeline_status": "completed"}


def _get_keywords() -> list[str]:
    """解析关键词配置"""
    raw = config.news_keywords.strip()
    if not raw:
        return []
    return [k.strip().lower() for k in raw.split(",") if k.strip()]


def _boost_keywords(items: list[dict], keywords: list[str]) -> list[dict]:
    """对匹配关键词的新闻进行加分"""
    for item in items:
        title = item.get("title", "").lower()
        summary = item.get("summary", "").lower()
        text = title + " " + summary
        matches = sum(1 for kw in keywords if kw.lower() in text)
        if matches > 0:
            item["importance_score"] = min(10, item.get("importance_score", 5) + matches)
            item["importance_reason"] = f"{item.get('importance_reason', '')} [匹配关键词: +{matches}]"
            item["_keyword_match"] = True
    return items


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
