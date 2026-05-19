from __future__ import annotations

import pytest

from app.tts.base_adapter import BaseTTSAdapter
from app.tts.adapter_registry import AdapterRegistry


class _MockTTSAdapter(BaseTTSAdapter):
    @property
    def provider_name(self) -> str:
        return "mock_provider"

    async def synthesize(self, text: str, voice: str, rate: str = "+0%", pitch: str = "+0Hz", volume: str = "+0%") -> bytes:
        return b"mock_audio_data"

    async def get_voices(self) -> list[dict]:
        return [{"name": "mock_voice", "locale": "zh-CN", "gender": "Male"}]


class _MockTTSAdapter2(BaseTTSAdapter):
    @property
    def provider_name(self) -> str:
        return "mock_provider_2"

    async def synthesize(self, text: str, voice: str, rate: str = "+0%", pitch: str = "+0Hz", volume: str = "+0%") -> bytes:
        return b"mock_audio_data_2"

    async def get_voices(self) -> list[dict]:
        return []


class TestAdapterRegistry:
    def test_register_and_get(self):
        registry = AdapterRegistry()
        adapter = _MockTTSAdapter()
        registry.register(adapter)
        assert registry.get("mock_provider") is adapter

    def test_get_unknown_raises(self):
        registry = AdapterRegistry()
        with pytest.raises(ValueError, match="Unknown TTS provider"):
            registry.get("nonexistent")

    def test_default_returns_first_registered(self):
        registry = AdapterRegistry()
        a1 = _MockTTSAdapter()
        a2 = _MockTTSAdapter2()
        registry.register(a1)
        registry.register(a2)
        assert registry.default is a1

    def test_list_providers(self):
        registry = AdapterRegistry()
        registry.register(_MockTTSAdapter())
        assert "mock_provider" in registry.list_providers()


@pytest.mark.asyncio
async def test_synthesize_returns_bytes():
    adapter = _MockTTSAdapter()
    result = await adapter.synthesize("hello", "voice1")
    assert isinstance(result, bytes)
    assert result == b"mock_audio_data"


@pytest.mark.asyncio
async def test_get_voices_returns_list():
    adapter = _MockTTSAdapter()
    voices = await adapter.get_voices()
    assert isinstance(voices, list)
    assert len(voices) == 1
    assert voices[0]["name"] == "mock_voice"
