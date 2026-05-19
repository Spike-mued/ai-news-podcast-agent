import asyncio
import hashlib
import os

from loguru import logger

from app.agents.podcast_writer.state import PodcastWriterState
from app.config import config
from app.tts.adapter_registry import adapter_registry
from app.utils.audio_utils import get_episode_path


# 角色→语音映射 — 参考 Podcast-Generator 的 podUsers 配置
_HOST_VOICE = config.tts_voice_zh
_EXPERT_VOICE = config.tts_voice_zh_expert


async def synthesize_audio(state: PodcastWriterState) -> dict:
    """使用 TTS 适配器将双人对话脚本合成为音频 — 每个对话轮次单独合成"""
    scripts = state.get("scripts", [])
    if not scripts:
        logger.warning("No scripts to synthesize")
        return {"audio_segments": [], "status": "completed"}

    # 展开对话轮次为独立 TTS 任务
    tts_tasks: list[dict] = []
    for script in scripts:
        dialogue = script.get("dialogue", [])
        if dialogue:
            for turn_idx, turn in enumerate(dialogue):
                speaker = turn.get("speaker", "")
                text = turn.get("text", "")
                if len(text) < 10:
                    continue
                tts_tasks.append({
                    **script,
                    "turn_index": turn_idx,
                    "speaker": speaker,
                    "text": text,
                    "total_turns": len(dialogue),
                })
        else:
            # 无 dialogue 字段 — 兼容旧格式（整段脚本作为主持人独白）
            text = script.get("script", "")
            if len(text) >= 10:
                tts_tasks.append({
                    **script,
                    "turn_index": 0,
                    "speaker": "",
                    "text": text,
                    "total_turns": 1,
                })

    audio_segments: list[dict] = []
    errors: list[str] = []
    semaphore = asyncio.Semaphore(3)

    async def synthesize_one(task: dict, global_index: int):
        async with semaphore:
            speaker = task.get("speaker", "")
            text = task.get("text", "")
            title = task.get("title", "untitled")
            language = task.get("language", "zh")
            score = task.get("importance_score", 5)
            turn_idx = task.get("turn_index", 0)

            # 根据角色选择语音
            if language == "en":
                voice = config.tts_voice_en
            elif speaker == "技术专家":
                voice = _EXPERT_VOICE
            else:
                voice = _HOST_VOICE

            # 根据重要性选择语速
            if score >= 8:
                rate = config.tts_rate_slow
            elif score >= 5:
                rate = config.tts_rate_normal
            else:
                rate = config.tts_rate_fast

            safe_name = hashlib.md5(f"{title}_{turn_idx}".encode()).hexdigest()[:12]
            filename = f"{global_index:04d}_{safe_name}.mp3"
            filepath = get_episode_path(filename)

            if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
                audio_segments.append({**task, "audio_path": filepath, "filename": filename})
                return

            try:
                adapter = adapter_registry.default
                await adapter.save(
                    text=text, voice=voice, filepath=filepath,
                    rate=rate, pitch=config.tts_pitch, volume=config.tts_volume,
                )
                audio_segments.append({**task, "audio_path": filepath, "filename": filename})
                logger.debug(f"TTS [{global_index + 1}/{len(tts_tasks)}] {speaker}: {text[:30]}... → {voice}")
            except Exception as e:
                logger.error(f"TTS failed [{global_index}]: {e}")
                errors.append(f"TTS failed: {title} turn {turn_idx}")

    tasks_coros = [synthesize_one(t, i) for i, t in enumerate(tts_tasks)]
    await asyncio.gather(*tasks_coros)

    logger.info(f"TTS: {len(audio_segments)}/{len(tts_tasks)} segments synthesized, {len(errors)} errors")
    return {"audio_segments": audio_segments, "errors": errors, "status": "completed"}
