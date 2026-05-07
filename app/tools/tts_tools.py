from langchain.tools import tool
from loguru import logger

from app.services.tts_service import tts_service


@tool
async def text_to_speech(text: str, title: str = "output", voice: str = "zh-CN-XiaoxiaoNeural") -> str:
    """将文本转换为语音，返回音频文件路径"""
    try:
        result = await tts_service.synthesize(text=text, title=title, voice=voice)
        return f"Audio generated: {result['audio_path']} (cached: {result['cached']})"
    except Exception as e:
        logger.error(f"text_to_speech failed: {e}")
        return f"Error: {e}"


@tool
async def list_tts_voices() -> str:
    """列出可用的中文 TTS 语音"""
    try:
        voices = await tts_service.get_available_voices()
        voice_list = [f"- {v['Name']} ({v['Locale']})" for v in voices[:10]]
        return "\n".join(voice_list) if voice_list else "No voices found"
    except Exception as e:
        return f"Error: {e}"
