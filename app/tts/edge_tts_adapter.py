from __future__ import annotations

import edge_tts

from app.tts.base_adapter import BaseTTSAdapter


class EdgeTTSAdapter(BaseTTSAdapter):
    """Microsoft Edge TTS 适配器 — 免费、无需 API Key"""

    @property
    def provider_name(self) -> str:
        return "edge_tts"

    async def synthesize(self, text: str, voice: str, rate: str = "+0%", pitch: str = "+0Hz", volume: str = "+0%") -> bytes:
        communicate = edge_tts.Communicate(
            text=text,
            voice=voice,
            rate=rate,
            pitch=pitch,
            volume=volume,
        )
        audio_chunks: list[bytes] = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])
        return b"".join(audio_chunks)

    async def save(self, text: str, voice: str, filepath: str, rate: str = "+0%", pitch: str = "+0Hz", volume: str = "+0%") -> None:
        communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch, volume=volume)
        await communicate.save(filepath)

    async def get_voices(self) -> list[dict]:
        voices = await edge_tts.VoicesManager.create()
        return [{"name": v["ShortName"], "locale": v["Locale"], "gender": v.get("Gender", "")} for v in voices.voices]
