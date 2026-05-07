from __future__ import annotations

from pathlib import Path

import yaml
from loguru import logger

from app.sources.base_source import BaseNewsSource
from app.sources.rss_source import RSSSource
from app.sources.web_scraper_source import WebScraperSource


class SourceRegistry:
    """新闻源注册表，从 YAML 配置加载和管理新闻源实例"""

    def __init__(self, config_path: str = "config/news_sources.yaml"):
        self.config_path = Path(config_path)
        self.sources: list[BaseNewsSource] = []
        self.collection_config: dict = {}
        self.dedup_config: dict = {}
        self.ranking_config: dict = {}
        self._load_config()

    def _load_config(self):
        if not self.config_path.exists():
            logger.warning(f"News sources config not found: {self.config_path}")
            return

        with open(self.config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        self.collection_config = config.get("collection", {})
        self.dedup_config = config.get("dedup", {})
        self.ranking_config = config.get("ranking", {})

        for src_cfg in config.get("sources", []):
            source = self._create_source(src_cfg)
            if source:
                self.sources.append(source)

        logger.info(f"Loaded {len(self.sources)} news sources from config")

    def _create_source(self, cfg: dict) -> BaseNewsSource | None:
        source_type = cfg.get("type", "").lower()
        name = cfg.get("name", "")
        url = cfg.get("url", "")
        if not name or not url:
            return None

        kwargs = {
            "timeout": self.collection_config.get("request_timeout", 30),
            "user_agent": self.collection_config.get("user_agent", "AI-News-Podcast-Agent/1.0"),
        }

        try:
            if source_type == "rss":
                return RSSSource(name=name, url=url, language=cfg.get("language", "zh"), priority=cfg.get("priority", 5), **kwargs)
            elif source_type in ("web", "web_scraper"):
                return WebScraperSource(name=name, url=url, language=cfg.get("language", "zh"), priority=cfg.get("priority", 5), **kwargs)
            else:
                logger.warning(f"Unknown source type: {source_type} for {name}")
                return None
        except Exception as e:
            logger.error(f"Failed to create source {name}: {e}")
            return None

    def get_sources(self, names: list[str] | None = None) -> list[BaseNewsSource]:
        if not names:
            return self.sources
        return [s for s in self.sources if s.name in names]

    def get_enabled_sources(self) -> list[BaseNewsSource]:
        return [s for s in self.sources]


source_registry = SourceRegistry()
