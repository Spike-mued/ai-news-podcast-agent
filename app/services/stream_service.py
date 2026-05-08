from __future__ import annotations

import asyncio
import os
import time
from collections import deque
from datetime import datetime

from loguru import logger

from app.config import config

# 全局流媒体状态
_stream_buffer: deque[bytes] = deque()
_stream_state = {
    "is_active": False,
    "current_file": None,
    "position": 0,
    "total_bytes": 0,
    "listeners": 0,
    "started_at": None,
}
_queue_lock = asyncio.Lock()


class StreamService:
    """HTTP 音频流服务"""

    def __init__(self):
        self.play_queue: list[dict] = []

    def add_to_queue(self, audio_path: str, duration: float = 0, metadata: dict | None = None):
        item = {
            "path": audio_path,
            "duration": duration,
            "metadata": metadata or {},
            "added_at": datetime.now().isoformat(),
            "played": False,
        }
        self.play_queue.append(item)
        logger.info(f"Stream queue: +{os.path.basename(audio_path)} ({duration:.1f}s), total={len(self.play_queue)}")

    def queue_length(self) -> int:
        return len(self.play_queue)

    def queue_duration(self) -> float:
        return sum(item.get("duration", 0) for item in self.play_queue)

    async def get_audio_chunk(self) -> bytes:
        """读取当前播放位置的音频数据块。队列空时循环最后一个文件，永不返回 None"""
        async with _queue_lock:
            if not self.play_queue:
                last = _stream_state.get("_last_file")
                if last and os.path.exists(last):
                    _stream_state["current_file"] = last
                    _stream_state["position"] = 0
                    _stream_state["total_bytes"] = os.path.getsize(last)
                    _stream_state["_looping"] = True
                else:
                    return b""  # 真的没有任何文件时返回空字节，但不中断流

            current = self.play_queue[0] if self.play_queue else {"path": _stream_state.get("_last_file", "")}
            filepath = current.get("path", "") if isinstance(current, dict) else ""

            if not filepath or not os.path.exists(filepath):
                if self.play_queue:
                    self.play_queue.pop(0)
                _stream_state["current_file"] = None
                _stream_state["position"] = 0
                return await self.get_audio_chunk()

            if _stream_state["current_file"] != filepath:
                _stream_state["_last_file"] = filepath
                _stream_state["current_file"] = filepath
                _stream_state["position"] = 0
                _stream_state["total_bytes"] = os.path.getsize(filepath)
                _stream_state["started_at"] = time.time()
                _stream_state["_looping"] = False

            try:
                with open(filepath, "rb") as f:
                    f.seek(_stream_state["position"])
                    chunk = f.read(config.stream_buffer_size)
                    if chunk:
                        _stream_state["position"] += len(chunk)
                        return chunk
                    else:
                        if self.play_queue:
                            self.play_queue.pop(0)
                        _stream_state["current_file"] = None
                        _stream_state["position"] = 0
                        return await self.get_audio_chunk()
            except Exception as e:
                logger.error(f"Stream read error: {e}")
                if self.play_queue:
                    self.play_queue.pop(0)
                return await self.get_audio_chunk()

    def get_status(self) -> dict:
        """获取当前播放状态"""
        current_item = self.play_queue[0] if self.play_queue else None
        return {
            "is_active": _stream_state["is_active"],
            "current_file": os.path.basename(_stream_state["current_file"] or ""),
            "position_bytes": _stream_state["position"],
            "total_bytes": _stream_state["total_bytes"],
            "listeners": _stream_state["listeners"],
            "queue_length": len(self.play_queue),
            "queue_duration": self.queue_duration(),
            "current_metadata": current_item.get("metadata") if current_item else None,
        }

    def listener_connected(self):
        _stream_state["listeners"] += 1
        _stream_state["is_active"] = True

    def listener_disconnected(self):
        _stream_state["listeners"] = max(0, _stream_state["listeners"] - 1)
        if _stream_state["listeners"] == 0:
            _stream_state["is_active"] = False


stream_service = StreamService()
