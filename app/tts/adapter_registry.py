from __future__ import annotations

from loguru import logger

from app.tts.base_adapter import BaseTTSAdapter
from app.tts.edge_tts_adapter import EdgeTTSAdapter


class AdapterRegistry:
    """TTS 适配器注册中心 — 参考 Podcast-Generator 的多 Provider 架构"""

    def __init__(self):
        self._adapters: dict[str, BaseTTSAdapter] = {}

    def register(self, adapter: BaseTTSAdapter) -> None:
        self._adapters[adapter.provider_name] = adapter
        logger.info(f"TTS adapter registered: {adapter.provider_name}")

    def get(self, name: str) -> BaseTTSAdapter:
        if name not in self._adapters:
            available = list(self._adapters.keys())
            logger.error(f"Unknown TTS provider '{name}', available: {available}")
            raise ValueError(f"Unknown TTS provider: '{name}'. Available: {available}")
        return self._adapters[name]

    @property
    def default(self) -> BaseTTSAdapter:
        """返回默认适配器 (edge_tts)"""
        return self._adapters.get("edge_tts", next(iter(self._adapters.values())))

    def list_providers(self) -> list[str]:
        return list(self._adapters.keys())


# 全局单例，注册默认 Provider
adapter_registry = AdapterRegistry()
adapter_registry.register(EdgeTTSAdapter())
