from __future__ import annotations

from abc import ABC, abstractmethod


class BaseTTSAdapter(ABC):
    """TTS 适配器抽象基类 — 参考 Podcast-Generator 的 provider-agnostic 模式"""

    @abstractmethod
    async def synthesize(self, text: str, voice: str, rate: str = "+0%", pitch: str = "+0Hz", volume: str = "+0%") -> bytes:
        """将文本转为语音，返回音频字节数据"""
        ...

    @abstractmethod
    async def get_voices(self) -> list[dict]:
        """返回该 Provider 支持的语音列表"""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider 标识名，如 'edge_tts', 'doubao'"""
        ...
