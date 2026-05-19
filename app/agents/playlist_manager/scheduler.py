from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from app.config import config

# 全局调度器
scheduler = AsyncIOScheduler()
pipeline_trigger_callbacks: list = []


def get_scheduler() -> AsyncIOScheduler:
    return scheduler


def register_trigger_callback(callback):
    """注册流水线触发回调"""
    pipeline_trigger_callbacks.append(callback)


async def start_scheduler():
    """启动定时调度器，周期触发新闻采集流水线"""
    interval = config.news_collection_interval_minutes

    scheduler.add_job(
        _trigger_pipeline,
        "interval",
        minutes=interval,
        id="pipeline_trigger",
        name=f"News pipeline every {interval}min",
        next_run_time=datetime.now(),  # 立即执行第一次
    )

    scheduler.add_job(
        _health_check_job,
        "interval",
        minutes=5,
        id="health_check",
        name="Health check",
    )

    # 每日凌晨 3 点自动归档过期数据
    scheduler.add_job(
        _archive_job,
        "cron",
        hour=3,
        minute=7,
        id="daily_archive",
        name="Daily data archive",
    )

    scheduler.start()
    logger.info(f"Scheduler started: pipeline every {interval} min, daily archive at 03:07")


async def stop_scheduler():
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")


async def trigger_now():
    """手动立即触发流水线"""
    await _trigger_pipeline()


async def _trigger_pipeline():
    logger.info("Scheduler: triggering pipeline...")
    for callback in pipeline_trigger_callbacks:
        try:
            if callable(callback):
                await callback()
        except Exception as e:
            logger.error(f"Pipeline callback error: {e}")


async def _health_check_job():
    from app.agents.playlist_manager.stream_manager import get_current_queue_status

    status = await get_current_queue_status()
    logger.debug(f"Health: queue={status['queue_length']}, playing={status['is_playing']}")


async def _archive_job():
    """每日自动归档：过期新闻 + 已播播客"""
    try:
        from app.api.archive import archive_all
        result = await archive_all()
        logger.info(f"Daily archive: {result['total']} items ({result['news_archived']} news, {result['podcasts_archived']} podcasts)")
    except Exception as e:
        logger.error(f"Daily archive failed: {e}")
