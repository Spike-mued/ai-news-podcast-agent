import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from loguru import logger

from app.services.stream_service import stream_service

router = APIRouter(tags=["stream"])


@router.get("/stream")
async def audio_stream(request: Request):
    """24小时不间断音频流端点 — 提供 audio/mpeg chunked 流"""
    stream_service.listener_connected()
    logger.info(f"Stream listener connected, total: {stream_service.get_status()['listeners']}")

    async def generate():
        try:
            while True:
                if await request.is_disconnected():
                    break

                chunk = await stream_service.get_audio_chunk()
                if chunk:
                    yield chunk
                else:
                    # 队列为空，发送极短的静音保持连接活跃
                    yield b""
                    await asyncio.sleep(0.5)
        finally:
            stream_service.listener_disconnected()
            logger.info("Stream listener disconnected")

    return StreamingResponse(
        generate(),
        media_type="audio/mpeg",
        headers={
            "Cache-Control": "no-cache",
            "Content-Type": "audio/mpeg",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


@router.get("/stream/status")
async def stream_status():
    return stream_service.get_status()
