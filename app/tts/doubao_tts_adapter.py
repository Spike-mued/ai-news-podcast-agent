from __future__ import annotations

from loguru import logger

from app.tts.base_adapter import BaseTTSAdapter


class DoubaoTTSAdapter(BaseTTSAdapter):
    """豆包 TTS 适配器 (预留) — 音质优于 edge-tts，需要火山引擎 API Key"""

    def __init__(self, app_id: str = "", access_key: str = ""):
        self._app_id = app_id
        self._access_key = access_key

    @property
    def provider_name(self) -> str:
        return "doubao"

    async def synthesize(self, text: str, voice: str, rate: str = "+0%", pitch: str = "+0Hz", volume: str = "+0%") -> bytes:
        logger.warning("Doubao TTS adapter not yet implemented — falling back to edge_tts")
        raise NotImplementedError("Doubao TTS adapter is a placeholder")

    async def get_voices(self) -> list[dict]:
        raise NotImplementedError("Doubao TTS adapter is a placeholder")
