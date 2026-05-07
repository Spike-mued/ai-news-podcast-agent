import asyncio
import hashlib
import os

import edge_tts
from loguru import logger

from app.agents.podcast_writer.state import PodcastWriterState
from app.config import config
from app.utils.audio_utils import get_episode_path


async def synthesize_audio(state: PodcastWriterState) -> dict:
    """使用 edge-tts 将脚本合成为音频"""
    scripts = state.get("scripts", [])
    if not scripts:
        logger.warning("No scripts to synthesize")
        return {"audio_segments": [], "status": "completed"}

    audio_segments: list[dict] = []
    errors: list[str] = []

    semaphore = asyncio.Semaphore(3)

    async def synthesize_one(script_item: dict, index: int):
        async with semaphore:
            script_text = script_item.get("script", "")
            title = script_item.get("title", "untitled")
            language = script_item.get("language", "zh")
            score = script_item.get("importance_score", 5)

            if language == "en":
                voice = config.tts_voice_en
            elif score >= 8:
                voice = config.tts_voice_zh
            else:
                voice = config.tts_voice_zh

            if score >= 8:
                rate = config.tts_rate_slow
            elif score >= 5:
                rate = config.tts_rate_normal
            else:
                rate = config.tts_rate_fast

            safe_name = hashlib.md5(title.encode()).hexdigest()[:12]
            filename = f"{index:03d}_{safe_name}.mp3"
            filepath = get_episode_path(filename)

            if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
                logger.debug(f"Audio exists: {filename}")
                audio_segments.append({**script_item, "audio_path": filepath, "filename": filename})
                return

            try:
                communicate = edge_tts.Communicate(
                    text=script_text,
                    voice=voice,
                    rate=rate,
                    pitch=config.tts_pitch,
                    volume=config.tts_volume,
                )
                await communicate.save(filepath)

                audio_segments.append({**script_item, "audio_path": filepath, "filename": filename})
                logger.info(f"TTS [{index + 1}/{len(scripts)}]: {title[:40]}... → {filename} (voice={voice}, rate={rate})")
            except Exception as e:
                logger.error(f"TTS failed for '{title}': {e}")
                errors.append(f"TTS failed: {title}")

    tasks = [synthesize_one(script, i) for i, script in enumerate(scripts)]
    await asyncio.gather(*tasks)

    logger.info(f"Synthesized {len(audio_segments)}/{len(scripts)} audio segments, {len(errors)} errors")
    return {"audio_segments": audio_segments, "errors": errors, "status": "completed"}
