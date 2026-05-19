from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

import httpx


class BaseNewsSource(ABC):
    """新闻源基类，所有新闻源适配器必须实现此接口"""

    def __init__(self, name: str, url: str, language: str = "zh", priority: int = 5, **kwargs):
        self.name = name
        self.url = url
        self.language = language
        self.priority = priority
        self.timeout = kwargs.get("timeout", 30)
        self.user_agent = kwargs.get("user_agent", "AI-News-Podcast-Agent/1.0")

    @abstractmethod
    async def fetch(self) -> list[dict]:
        """获取新闻列表，返回标准化格式"""
        ...

    def _normalize_item(self, title: str, url: str, summary: str = "", published_at: str | None = None) -> dict:
        return {
            "title": title.strip(),
            "url": url.strip(),
            "summary": summary.strip(),
            "source": self.name,
            "source_type": self.source_type,
            "language": self.language,
            "priority_weight": self.priority,
            "published_at": published_at or datetime.now().isoformat(),
            "collected_at": datetime.now().isoformat(),
        }

    @property
    @abstractmethod
    def source_type(self) -> str:
        ...

    async def _fetch_url(self, url: str) -> str:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url, headers={"User-Agent": self.user_agent}, follow_redirects=True)
            resp.raise_for_status()
            return resp.text
