import os
import subprocess
from pathlib import Path

from loguru import logger

from app.config import config
from app.utils.audio_utils import ensure_audio_dirs, get_asset_path, get_episode_path, get_playlist_path

# 自动查找 ffmpeg 路径
_FFMPEG_PATH = None
_FFPROBE_PATH = None
for _p in [
    r"C:\Users\Administrator\ffmpeg\ffmpeg-8.1.1-essentials_build\bin",
    r"C:\ffmpeg\bin",
    os.path.expandvars(r"%ProgramFiles%\ffmpeg\bin"),
]:
    _ff = os.path.join(_p, "ffmpeg.exe")
    _fp = os.path.join(_p, "ffprobe.exe")
    if os.path.exists(_ff):
        _FFMPEG_PATH = _ff
        _FFPROBE_PATH = _fp
        os.environ["PATH"] = _p + os.pathsep + os.environ.get("PATH", "")
        break


class AudioService:
    """音频处理服务"""

    def __init__(self):
        ensure_audio_dirs()
        self._setup_pydub()

    def _setup_pydub(self):
        if _FFMPEG_PATH and _FFPROBE_PATH:
            try:
                from pydub import AudioSegment
                AudioSegment.converter = _FFMPEG_PATH
                AudioSegment.ffmpeg = _FFMPEG_PATH
                AudioSegment.ffprobe = _FFPROBE_PATH
                logger.info(f"pydub configured with ffmpeg: {_FFMPEG_PATH}")
            except ImportError:
                pass

    def concatenate(self, audio_files: list[str], output_filename: str, crossfade_ms: int = 800) -> str:
        """将多个音频文件拼接为一个，添加交叉淡入淡出和过渡音效"""
        try:
            from pydub import AudioSegment
        except ImportError:
            logger.error("pydub not installed, using simple file concatenation")
            return self._simple_concat(audio_files, output_filename)

        combined = AudioSegment.empty()

        for i, filepath in enumerate(audio_files):
            if not os.path.exists(filepath):
                logger.warning(f"Audio file not found: {filepath}")
                continue

            try:
                segment = AudioSegment.from_file(filepath)
            except Exception as e:
                logger.error(f"Failed to load {filepath}: {e}")
                continue

            if len(combined) > 0 and len(segment) > 0:
                # 快速平滑过渡：300ms 交叉淡入淡出，无静音间隔
                transition_ms = 300
                combined = combined.fade_out(transition_ms) + segment.fade_in(transition_ms)
            else:
                combined = segment

        if len(combined) == 0:
            logger.error("No valid audio segments to concatenate")
            return self._simple_concat(audio_files, output_filename)

        combined = combined.set_frame_rate(config.audio_sample_rate)

        # 整体音量归一化
        try:
            change = -16.0 - combined.dBFS
            combined = combined.apply_gain(change)
        except Exception:
            pass

        output_path = get_playlist_path(output_filename)
        combined.export(output_path, format=config.audio_format, bitrate=config.stream_bitrate)
        logger.info(f"Concatenated {len(audio_files)} files → {output_path} ({len(combined) / 1000:.1f}s, {len(combined)/1000/60:.1f}min)")
        return output_path

    def _simple_concat(self, audio_files: list[str], output_filename: str) -> str:
        """简单的二进制拼接 + 静音间隔（fallback，不需要 ffmpeg）"""
        output_path = get_playlist_path(output_filename)
        silence = b'\x00' * 8000  # ~0.5s silence at 128kbps MP3
        with open(output_path, "wb") as out:
            for i, f in enumerate(audio_files):
                if os.path.exists(f):
                    with open(f, "rb") as inf:
                        out.write(inf.read())
                    if i < len(audio_files) - 1:
                        out.write(silence)
        logger.info(f"Simple concat: {len(audio_files)} files → {output_path}")
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
