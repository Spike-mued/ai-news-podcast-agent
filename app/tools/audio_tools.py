from langchain.tools import tool
from loguru import logger

from app.services.audio_service import audio_service
from app.utils.audio_utils import get_audio_duration_seconds, validate_audio_file


@tool
async def concatenate_audio_files(files_json: str, output_name: str = "playlist") -> str:
    """将多个音频文件拼接为一个，files_json 为文件路径的 JSON 数组字符串"""
    import json

    try:
        file_list = json.loads(files_json)
        if not isinstance(file_list, list):
            return "Error: files_json must be a JSON array of file paths"
        output = audio_service.concatenate(file_list, f"{output_name}.mp3")
        return f"Concatenated {len(file_list)} files → {output}"
    except Exception as e:
        logger.error(f"concatenate failed: {e}")
        return f"Error: {e}"


@tool
async def get_audio_info(filepath: str) -> str:
    """获取音频文件的信息（时长、大小）"""
    import os

    if not validate_audio_file(filepath):
        return "Error: file not found or invalid"

    duration = get_audio_duration_seconds(filepath)
    size = os.path.getsize(filepath)
    return f"File: {os.path.basename(filepath)}, Duration: {duration:.1f}s, Size: {size} bytes"


@tool
async def normalize_audio_volume(filepath: str) -> str:
    """规范化音频文件的音量"""
    try:
        result = audio_service.normalize_volume(filepath)
        return f"Normalized: {result}"
    except Exception as e:
        return f"Error: {e}"
