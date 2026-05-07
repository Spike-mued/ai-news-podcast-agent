from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "ai-news-podcast-agent",
        "version": "0.1.0",
        "components": {
            "api": "ok",
            "database": "ok",
            "llm": "ok",
        },
    }
