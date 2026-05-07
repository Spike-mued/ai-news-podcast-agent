import os
from pathlib import Path

from loguru import logger

from app.config import config
from app.utils.audio_utils import ensure_audio_dirs, get_asset_path, get_episode_path, get_playlist_path


class AudioService:
    """音频处理服务"""

    def __init__(self):
        ensure_audio_dirs()

    def concatenate(self, audio_files: list[str], output_filename: str, crossfade_ms: int = 500) -> str:
        """将多个音频文件拼接为一个，添加交叉淡入淡出"""
        try:
            from pydub import AudioSegment
        except ImportError:
            logger.error("pydub not installed, using simple file concatenation")
            return self._simple_concat(audio_files, output_filename)

        output_path = get_playlist_path(output_filename)
        combined = AudioSegment.empty()

        for i, filepath in enumerate(audio_files):
            if not os.path.exists(filepath):
                logger.warning(f"Audio file not found: {filepath}")
                continue

            segment = AudioSegment.from_file(filepath)

            if crossfade_ms > 100 and i > 0 and len(combined) > 0:
                combined = combined.append(segment, crossfade=crossfade_ms)
            else:
                combined += segment

            # 添加短暂静音间隔
            combined += AudioSegment.silent(duration=300)

        combined = combined.set_frame_rate(config.audio_sample_rate)

        output_path = get_playlist_path(output_filename)
        combined.export(output_path, format=config.audio_format, bitrate=config.stream_bitrate)
        logger.info(f"Concatenated {len(audio_files)} files → {output_path} ({len(combined) / 1000:.1f}s)")
        return output_path

    def _simple_concat(self, audio_files: list[str], output_filename: str) -> str:
        """简单的二进制拼接（fallback）"""
        output_path = get_playlist_path(output_filename)
        with open(output_path, "wb") as out:
            for f in audio_files:
                if os.path.exists(f):
                    with open(f, "rb") as inf:
                        out.write(inf.read())
        return output_path

    def get_duration(self, filepath: str) -> float:
        try:
            from pydub import AudioSegment

            audio = AudioSegment.from_file(filepath)
            return len(audio) / 1000.0
        except Exception:
            return 0.0

    def add_silence(self, filepath: str, silence_ms: int = 500) -> str:
        try:
            from pydub import AudioSegment

            audio = AudioSegment.from_file(filepath)
            silenced = AudioSegment.silent(duration=silence_ms) + audio + AudioSegment.silent(duration=silence_ms)
            silenced.export(filepath, format=config.audio_format, bitrate=config.stream_bitrate)
            return filepath
        except Exception:
            return filepath

    def normalize_volume(self, filepath: str, target_dbfs: float = -16.0) -> str:
        try:
            from pydub import AudioSegment

            audio = AudioSegment.from_file(filepath)
            change = target_dbfs - audio.dBFS
            normalized = audio.apply_gain(change)
            normalized.export(filepath, format=config.audio_format, bitrate=config.stream_bitrate)
            return filepath
        except Exception:
            return filepath


audio_service = AudioService()
