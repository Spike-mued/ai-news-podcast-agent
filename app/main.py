from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from app.api.health import router as health_router
from app.api.news import router as news_router
from app.api.podcast import router as podcast_router
from app.api.sources import router as sources_router
from app.api.stream import router as stream_router
from app.agents.playlist_manager.scheduler import start_scheduler, stop_scheduler
from app.config import config
from app.core.database import init_database
from app.utils.logger import LOG_DIR  # noqa: F401 - ensure logger is configured


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {config.app_name} v0.1.0")
    logger.info(f"Debug mode: {config.debug}")
    await init_database()
    await start_scheduler()
    logger.info(f"Server running on http://{config.host}:{config.port}")
    yield
    await stop_scheduler()
    logger.info("Shutting down...")


app = FastAPI(
    title=config.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
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
    index_path = "static/index.html"
    try:
        return FileResponse(index_path)
    except FileNotFoundError:
        return {
            "name": config.app_name,
            "version": "0.1.0",
            "docs": "/docs",
            "health": "/api/health",
            "api": {
                "news": "/api/news",
                "podcasts": "/api/podcasts",
                "stream": "/stream",
                "pipeline": "POST /api/pipeline/trigger",
            },
        }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=config.host,
        port=config.port,
        reload=config.debug,
    )
