from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from app.api.archive import router as archive_router
from app.api.chat import router as chat_router
from app.api.health import router as health_router
from app.api.model_connections import router as model_connections_router
from app.api.news import router as news_router
from app.api.podcast import router as podcast_router
from app.api.sources import router as sources_router
from app.api.stream import router as stream_router
from app.agents.playlist_manager.scheduler import start_scheduler, stop_scheduler
from app.config import config
from app.core.database import init_database
from app.utils.logger import LOG_DIR  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {config.app_name} v0.2.0")
    logger.info(f"Debug mode: {config.debug}")
    await init_database()
    await start_scheduler()
    # 启动后自动检测时间窗口新闻是否就绪
    asyncio.create_task(_startup_check())
    logger.info(f"Server running on http://{config.host}:{config.port}")
    yield
    await stop_scheduler()
    logger.info("Shutting down...")


async def _startup_check():
    """启动自动化：检测昨天8:00→今天8:00窗口是否有新闻，缺则自动采集"""
    await asyncio.sleep(3)  # 等服务完全启动
    from app.rag.chroma_store import check_window_has_news
    from app.services.pipeline_service import run_full_pipeline

    has_news = check_window_has_news()
    if not has_news:
        logger.info("Startup: time window news missing → auto-triggering pipeline")
        try:
            result = await run_full_pipeline()
            logger.info(f"Startup pipeline: {result.get('success')}")
        except Exception as e:
            logger.error(f"Startup pipeline failed: {e}")
    else:
        logger.info("Startup: time window news already collected, skipping")


app = FastAPI(
    title=config.app_name,
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(archive_router)
app.include_router(chat_router)
app.include_router(health_router)
app.include_router(model_connections_router)
app.include_router(news_router)
app.include_router(podcast_router)
app.include_router(sources_router)
app.include_router(stream_router)

try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except RuntimeError:
    pass


@app.get("/")
async def root():
    try:
        return FileResponse("static/index.html")
    except FileNotFoundError:
        return {
            "name": config.app_name,
            "version": "0.2.0",
            "docs": "/docs",
            "chat": "/chat",
        }


@app.get("/chat")
async def chat_page():
    try:
        return FileResponse("static/chat.html")
    except FileNotFoundError:
        return {"error": "chat page not found"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=config.host,
        port=config.port,
        reload=config.debug,
    )
