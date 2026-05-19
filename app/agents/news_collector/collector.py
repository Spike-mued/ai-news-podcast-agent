import asyncio

from loguru import logger

from app.agents.news_collector.state import NewsCollectorState
from app.sources.base_source import BaseNewsSource
from app.sources.source_registry import source_registry


async def collect_news(state: NewsCollectorState) -> dict:
    """从多个新闻源并行采集新闻"""
    sources = state.get("sources", [])

    await source_registry.load_from_db()
    source_instances = source_registry.get_sources(sources) if sources else source_registry.get_enabled_sources()
    max_concurrent = source_registry.collection_config.get("max_concurrent", 5)

    if not source_instances:
        logger.warning("No news sources configured")
        return {"fetch_errors": ["No news sources configured"]}

    logger.info(f"Collecting news from {len(source_instances)} sources")
    semaphore = asyncio.Semaphore(max_concurrent)

    async def fetch_with_limit(source: BaseNewsSource) -> list[dict]:
        async with semaphore:
            try:
                return await source.fetch()
            except Exception as e:
                logger.error(f"Error fetching {source.name}: {e}")
                return []

    tasks = [fetch_with_limit(s) for s in source_instances]
    results = await asyncio.gather(*tasks)

    all_news: list[dict] = []
    errors: list[str] = []

    for source, items in zip(source_instances, results):
        if isinstance(items, Exception):
            errors.append(f"{source.name}: {str(items)}")
        else:
            all_news.extend(items)

    logger.info(f"Collected {len(all_news)} raw news items, {len(errors)} errors")
    return {"raw_news": all_news, "fetch_errors": errors}
