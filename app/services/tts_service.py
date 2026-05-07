from __future__ import annotations

import asyncio
import hashlib
import os

import edge_tts
from loguru import logger

from app.config import config
from app.utils.audio_utils import get_episode_path


class TTSService:
    """TTS 合成服务封装"""

    async def synthesize(
        self, text: str, title: str = "untitled", voice: str | None = None, language: str = "zh"
    ) -> dict:
        if voice is None:
            voice = config.tts_voice if language == "zh" else "en-US-JennyNeural"

        safe_name = hashlib.md5(title.encode()).hexdigest()[:12]
        filename = f"{safe_name}.mp3"
        filepath = get_episode_path(filename)

        if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
            return {"audio_path": filepath, "filename": filename, "cached": True}

        try:
            communicate = edge_tts.Communicate(
                text=text, voice=voice, rate=config.tts_rate, volume=config.tts_volume
            )
            await communicate.save(filepath)
            return {"audio_path": filepath, "filename": filename, "cached": False}
        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}")
            raise

    async def batch_synthesize(self, items: list[dict], max_concurrent: int = 3) -> list[dict]:
        semaphore = asyncio.Semaphore(max_concurrent)

        async def synth_one(item: dict, index: int):
            async with semaphore:
                try:
                    result = await self.synthesize(
                        text=item["script"],
                        title=item.get("title", f"news_{index}"),
                        language=item.get("language", "zh"),
                    )
                    return {**item, **result, "index": index}
                except Exception as e:
                    return {**item, "error": str(e), "index": index}

        tasks = [synth_one(item, i) for i, item in enumerate(items)]
        results = await asyncio.gather(*tasks)

        success = [r for r in results if "error" not in r]
        failed = [r for r in results if "error" in r]
        logger.info(f"Batch TTS: {len(success)} success, {len(failed)} failed")
        return results

    async def get_available_voices(self) -> list[dict]:
        voices = await edge_tts.VoicesManager.create()
        chinese_voices = [v for v in voices.voices if "zh" in v["Locale"]]
        return chinese_voices


tts_service = TTSService()
