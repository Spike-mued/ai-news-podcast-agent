from __future__ import annotations

import asyncio
import os
from collections import deque
from datetime import datetime, timedelta

from loguru import logger

from app.agents.playlist_manager.state import PlaylistManagerState
from app.config import config

# 全局播放队列（环形缓冲区）
play_queue: deque[dict] = deque(maxlen=50)
stream_state: dict = {
    "is_playing": False,
    "current_file": None,
    "position_bytes": 0,
    "total_bytes": 0,
    "started_at": None,
    "listeners": 0,
}


def _get_next_trigger_time() -> str:
    interval = config.news_collection_interval_minutes
    next_time = datetime.now() + timedelta(minutes=interval)
    return next_time.strftime("%Y-%m-%d %H:%M:%S")


async def manage_stream_queue(state: PlaylistManagerState) -> dict:
    """管理流媒体播放队列"""
    playlist_path = state.get("playlist_path", "")
    duration = state.get("playlist_duration", 0)

    if playlist_path and os.path.exists(playlist_path):
        queue_item = {
            "path": playlist_path,
            "duration": duration,
            "added_at": datetime.now().isoformat(),
            "played": False,
        }
        play_queue.append(queue_item)
        logger.info(f"Added to queue: {os.path.basename(playlist_path)} ({duration:.1f}s)")

    queue_length = len(play_queue)

    # 检查队列是否需要补充
    total_queued = sum(item.get("duration", 0) for item in play_queue)
    if total_queued < 1800:  # 少于30分钟
        logger.warning(f"Queue running low: {total_queued:.0f}s remaining")

    next_trigger = _get_next_trigger_time()

    return {
        "queue_length": queue_length,
        "next_trigger_time": next_trigger,
        "stream_status": "playing" if stream_state["is_playing"] else "ready",
    }


async def get_current_queue_status() -> dict:
    return {
        "queue_length": len(play_queue),
        "is_playing": stream_state["is_playing"],
        "current_file": stream_state["current_file"],
        "position_bytes": stream_state["position_bytes"],
        "total_bytes": stream_state["total_bytes"],
        "listeners": stream_state["listeners"],
    }


async def get_next_audio_chunk() -> bytes | None:
    """从播放队列中获取下一个音频块（用于流式输出）"""
    if not play_queue:
        return None

    current = play_queue[0]
    filepath = current.get("path", "")

    if not filepath or not os.path.exists(filepath):
        play_queue.popleft()
        return await get_next_audio_chunk()

    try:
        chunk_size = config.stream_buffer_size

        if stream_state["current_file"] != filepath:
            stream_state["current_file"] = filepath
            stream_state["position_bytes"] = 0
            stream_state["total_bytes"] = os.path.getsize(filepath)
            stream_state["started_at"] = datetime.now()
            stream_state["is_playing"] = True

        with open(filepath, "rb") as f:
            f.seek(stream_state["position_bytes"])
            chunk = f.read(chunk_size)
            if not chunk:
                # 当前文件播放完毕，移到下一个
                play_queue.popleft()
                stream_state["current_file"] = None
                stream_state["position_bytes"] = 0
                return await get_next_audio_chunk()

            stream_state["position_bytes"] += len(chunk)
            return chunk
    except Exception as e:
        logger.error(f"Stream read error: {e}")
        play_queue.popleft()
        return await get_next_audio_chunk()
