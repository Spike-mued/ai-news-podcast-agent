import asyncio
import hashlib
from datetime import datetime

import feedparser
from loguru import logger

from app.core.constants import SOURCE_TYPE_RSS
from app.sources.base_source import BaseNewsSource


class RSSSource(BaseNewsSource):
    """RSS/Atom Feed 新闻源适配器"""

    def __init__(self, name: str, url: str, language: str = "zh", priority: int = 5, **kwargs):
        super().__init__(name, url, language, priority, **kwargs)

    @property
    def source_type(self) -> str:
        return SOURCE_TYPE_RSS

    async def fetch(self) -> list[dict]:
        logger.info(f"[RSS] Fetching from {self.name}: {self.url}")
        try:
            loop = asyncio.get_running_loop()
            feed = await loop.run_in_executor(None, feedparser.parse, self.url)
        except Exception as e:
            logger.error(f"[RSS] Failed to parse feed {self.name}: {e}")
            return []

        if feed.bozo and not feed.entries:
            logger.warning(f"[RSS] Feed {self.name} is malformed: {feed.bozo_exception}")
            return []

        results = []
        for entry in feed.entries[:20]:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            if not title or not link:
                continue

            summary = ""
            if "summary" in entry:
                summary = entry.summary
            elif "description" in entry:
                summary = entry.description
            elif "content" in entry:
                summary = entry.content[0].get("value", "")

            published = None
            if "published_parsed" in entry and entry.published_parsed:
                try:
                    published = datetime(*entry.published_parsed[:6]).isoformat()
                except (ValueError, TypeError):
                    pass
            if not published and "updated_parsed" in entry and entry.updated_parsed:
                try:
                    published = datetime(*entry.updated_parsed[:6]).isoformat()
                except (ValueError, TypeError):
                    pass

            content_hash = hashlib.md5(f"{title}{link}".encode()).hexdigest()
            item = self._normalize_item(title, link, summary, published)
            item["content_hash"] = content_hash
            item["raw_data"] = str(entry.get("id", ""))
            results.append(item)

        logger.info(f"[RSS] {self.name}: fetched {len(results)} items")
        return results
