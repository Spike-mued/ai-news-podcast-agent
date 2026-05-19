"""Chroma 向量存储 — 双层 Collection：日库 + 总库"""
from __future__ import annotations

from datetime import datetime, timedelta

import chromadb
from chromadb.config import Settings as ChromaSettings
from loguru import logger

from app.config import config

_client: chromadb.PersistentClient | None = None


def _get_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(
            path=str(config.chroma_path),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    return _client


def _daily_collection_name(date_str: str | None = None) -> str:
    """生成当日子库 Collection 名称"""
    if date_str is None:
        date_str = datetime.now().strftime("%Y%m%d")
    return f"news_{date_str}"


GLOBAL_COLLECTION = "news_global"


def _get_or_create_collection(name: str) -> chromadb.Collection:
    client = _get_client()
    try:
        return client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )
    except Exception:
        return client.create_collection(name=name, metadata={"hnsw:space": "cosine"})


def index_news(news_items: list[dict], date_str: str | None = None):
    """将新闻批量写入 Chroma：同时写入日库 + 总库"""
    if not news_items:
        return

    if date_str is None:
        date_str = datetime.now().strftime("%Y%m%d")

    daily_col = _get_or_create_collection(_daily_collection_name(date_str))
    global_col = _get_or_create_collection(GLOBAL_COLLECTION)

    ids: list[str] = []
    docs: list[str] = []
    metadatas: list[dict] = []

    for item in news_items:
        uid = item.get("url", "") or item.get("title", "")
        doc = f"{item.get('title', '')}\n{item.get('summary', '')}\n来源: {item.get('source', '')}"
        meta = {
            "title": item.get("title", ""),
            "source": item.get("source", ""),
            "url": item.get("url", ""),
            "score": item.get("importance_score", 5),
            "date": date_str,
        }
        ids.append(uid)
        docs.append(doc)
        metadatas.append(meta)

    try:
        daily_col.add(ids=ids, documents=docs, metadatas=metadatas)
    except Exception as e:
        logger.warning(f"Chroma daily index: {e}")

    try:
        global_col.add(ids=ids, documents=docs, metadatas=metadatas)
    except Exception as e:
        logger.warning(f"Chroma global index: {e}")

    logger.info(f"Chroma indexed {len(ids)} docs → {_daily_collection_name(date_str)} + {GLOBAL_COLLECTION}")


def search_news(query: str, source: str = "daily", date_str: str | None = None, top_k: int = 5) -> list[dict]:
    """检索新闻：source='daily' 查日库，source='global' 查总库"""
    if source == "daily":
        if date_str is None:
            date_str = datetime.now().strftime("%Y%m%d")
        col = _get_or_create_collection(_daily_collection_name(date_str))
    else:
        col = _get_or_create_collection(GLOBAL_COLLECTION)

    try:
        results = col.query(query_texts=[query], n_results=top_k)
        if not results or not results.get("ids") or not results["ids"][0]:
            return []

        items = []
        for i in range(len(results["ids"][0])):
            meta = results["metadatas"][0][i] if results.get("metadatas") else {}
            items.append({
                "title": meta.get("title", ""),
                "source": meta.get("source", ""),
                "url": meta.get("url", ""),
                "score": meta.get("score", 5),
                "date": meta.get("date", ""),
                "content": results["documents"][0][i] if results.get("documents") else "",
            })
        return items
    except Exception as e:
        logger.warning(f"Chroma search failed: {e}")
        return []


def get_daily_news_count(date_str: str | None = None) -> int:
    """获取当日 Chroma 日库中的新闻数量"""
    if date_str is None:
        date_str = datetime.now().strftime("%Y%m%d")
    try:
        col = _get_or_create_collection(_daily_collection_name(date_str))
        return col.count()
    except Exception:
        return 0


def check_window_has_news(days_ago: int = 1) -> bool:
    """检查时间窗口(昨天8:00→今天8:00)是否有新闻"""
    from zoneinfo import ZoneInfo
    tz = ZoneInfo("Asia/Shanghai")
    now = datetime.now(tz)
    today_8am = now.replace(hour=8, minute=0, second=0, microsecond=0)
    target_date = (now - timedelta(days=days_ago)).strftime("%Y%m%d")
    # 如果当前时间在 8:00 之前，检查前一天
    if now < today_8am:
        target_date = (now - timedelta(days=days_ago + 1)).strftime("%Y%m%d")
    count = get_daily_news_count(target_date)
    return count > 0
