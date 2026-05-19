import hashlib

from bs4 import BeautifulSoup
from loguru import logger

from app.core.constants import SOURCE_TYPE_WEB
from app.sources.base_source import BaseNewsSource


class WebScraperSource(BaseNewsSource):
    """网页爬虫新闻源适配器，从 HTML 页面提取链接和标题"""

    def __init__(self, name: str, url: str, language: str = "zh", priority: int = 5, **kwargs):
        super().__init__(name, url, language, priority, **kwargs)
        self.article_selector = kwargs.get("article_selector", "article")
        self.title_selector = kwargs.get("title_selector", "h2 a, h3 a, .title a")
        self.link_selector = kwargs.get("link_selector", "a")

    @property
    def source_type(self) -> str:
        return SOURCE_TYPE_WEB

    async def fetch(self) -> list[dict]:
        logger.info(f"[Web] Fetching from {self.name}: {self.url}")
        try:
            html = await self._fetch_url(self.url)
        except Exception as e:
            logger.error(f"[Web] Failed to fetch {self.name}: {e}")
            return []

        soup = BeautifulSoup(html, "html.parser")
        seen_urls = set()
        results = []

        for link in soup.select(self.title_selector):
            title = link.get_text(strip=True)
            href = link.get("href", "")
            if not title or not href or len(title) < 5:
                continue

            if not href.startswith("http"):
                from urllib.parse import urljoin

                href = urljoin(self.url, href)

            if href in seen_urls:
                continue
            seen_urls.add(href)

            content_hash = hashlib.md5(f"{title}{href}".encode()).hexdigest()

            parent = link.find_parent("article") or link.find_parent("div")
            summary = ""
            if parent:
                text = parent.get_text(strip=True)
                if len(text) > len(title):
                    summary = text[:300]

            item = self._normalize_item(title, href, summary)
            item["content_hash"] = content_hash
            results.append(item)

        logger.info(f"[Web] {self.name}: fetched {len(results)} items")
        return results
