from __future__ import annotations

from pathlib import Path

import aiosqlite
import yaml
from loguru import logger

from app.config import config
from app.sources.base_source import BaseNewsSource
from app.sources.rss_source import RSSSource
from app.sources.web_scraper_source import WebScraperSource


class SourceRegistry:
    """新闻源注册表，支持从 YAML 种子 + 数据库动态管理"""

    def __init__(self, config_path: str = "config/news_sources.yaml"):
        self.config_path = Path(config_path)
        self.sources: list[BaseNewsSource] = []
        self.collection_config: dict = {}
        self.dedup_config: dict = {}
        self.ranking_config: dict = {}
        self._load_yaml_config()

    def _load_yaml_config(self):
        if not self.config_path.exists():
            logger.warning(f"News sources config not found: {self.config_path}")
            return
        with open(self.config_path, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f)
        self.collection_config = config_data.get("collection", {})
        self.dedup_config = config_data.get("dedup", {})
        self.ranking_config = config_data.get("ranking", {})

    async def load_from_db(self):
        """从数据库加载已启用的新闻源"""
        try:
            db = await aiosqlite.connect(config.database_path)
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM news_sources WHERE is_enabled = 1 ORDER BY priority DESC")
            rows = await cursor.fetchall()
            await db.close()

            self.sources = []
            timeout = self.collection_config.get("request_timeout", 30)
            user_agent = self.collection_config.get("user_agent", "AI-News-Podcast-Agent/1.0")

            for row in rows:
                src_dict = dict(row)
                src_type = src_dict.get("type", "rss")
                kwargs = {"timeout": timeout, "user_agent": user_agent}
                src = self._create_source_from_dict(src_dict, src_type, **kwargs)
                if src:
                    self.sources.append(src)

            logger.info(f"Loaded {len(self.sources)} sources from database")
        except Exception as e:
            logger.error(f"Failed to load sources from DB: {e}")

    @staticmethod
    def _create_source_from_dict(cfg: dict, source_type: str, **kwargs) -> BaseNewsSource | None:
        name = cfg.get("name", "")
        url = cfg.get("url", "")
        if not name or not url:
            return None
        try:
            if source_type == "rss":
                return RSSSource(name=name, url=url, language=cfg.get("language", "zh"), priority=cfg.get("priority", 5), **kwargs)
            elif source_type in ("web", "web_scraper"):
                return WebScraperSource(name=name, url=url, language=cfg.get("language", "zh"), priority=cfg.get("priority", 5), **kwargs)
            return None
        except Exception as e:
            logger.error(f"Failed to create source {name}: {e}")
            return None

    def get_sources(self, names: list[str] | None = None) -> list[BaseNewsSource]:
        if not names:
            return self.sources
        return [s for s in self.sources if s.name in names]

    def get_enabled_sources(self) -> list[BaseNewsSource]:
        return self.sources


source_registry = SourceRegistry()


async def reload_registry():
    """重新加载新闻源（从数据库）"""
    await source_registry.load_from_db()
    logger.info("Source registry reloaded")
