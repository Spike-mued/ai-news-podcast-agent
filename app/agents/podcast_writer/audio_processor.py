import os

from loguru import logger

from app.agents.podcast_writer.state import PodcastWriterState
from app.utils.audio_utils import get_audio_duration_seconds, validate_audio_file


async def process_audio_segments(state: PodcastWriterState) -> dict:
    """对合成的音频片段进行后处理：验证、规范化、添加元数据"""
    audio_segments = state.get("audio_segments", [])
    if not audio_segments:
        logger.warning("No audio segments to process")
        return {"audio_segments": [], "status": "completed"}

    processed: list[dict] = []
    errors: list[str] = []

    for seg in audio_segments:
        filepath = seg.get("audio_path", "")
        if not filepath or not validate_audio_file(filepath):
            errors.append(f"Invalid audio: {seg.get('title', 'unknown')}")
            continue

        try:
            duration = get_audio_duration_seconds(filepath)
            seg["audio_duration"] = duration
            seg["audio_size"] = os.path.getsize(filepath)
            processed.append(seg)
            logger.debug(f"Audio OK: {seg.get('filename')} ({duration:.1f}s)")
        except Exception as e:
            logger.error(f"Audio processing failed for {filepath}: {e}")
            errors.append(f"Processing failed: {seg.get('title', 'unknown')}")
            processed.append(seg)

    logger.info(f"Processed {len(processed)} audio segments")
    return {"audio_segments": processed, "errors": errors, "status": "completed"}
