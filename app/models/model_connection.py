from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ModelConnection(BaseModel):
    id: int | None = None
    name: str
    service_type: str  # "llm" | "tts"
    provider: str
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    voice: str = ""
    extra_config: str = "{}"
    is_active: bool = False
    created_at: str | None = None


class ModelConnectionList(BaseModel):
    items: list[ModelConnection]
    active_llm: ModelConnection | None = None
    active_tts: ModelConnection | None = None


class ModelConnectionRequest(BaseModel):
    name: str
    service_type: str
    provider: str
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    voice: str = ""
    extra_config: str = "{}"
    is_active: bool = False


# 预置支持的服务列表（供前端展示）
SUPPORTED_SERVICES: dict[str, list[dict[str, Any]]] = {
    "llm": [
        {
            "provider": "dashscope",
            "display": "阿里云 DashScope（通义千问）",
            "models": ["qwen-plus", "qwen-max", "qwen-turbo", "qwen3.5-122b-a10b", "qwen3.5-32b-a10b"],
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "requires_api_key": True,
        },
        {
            "provider": "openai",
            "display": "OpenAI",
            "models": ["gpt-4o", "gpt-4-turbo", "gpt-4o-mini", "gpt-3.5-turbo"],
            "base_url": "https://api.openai.com/v1",
            "requires_api_key": True,
        },
        {
            "provider": "custom_openai",
            "display": "自定义兼容接口（vLLM / LiteLLM / Ollama 等）",
            "models": [],
            "base_url": "http://localhost:8000/v1",
            "requires_api_key": False,
        },
    ],
    "tts": [
        {
            "provider": "edge_tts",
            "display": "Microsoft Edge TTS（免费）",
            "models": [],
            "voices": {
                "zh-CN": ["zh-CN-YunxiNeural (男·沉稳)", "zh-CN-YunyangNeural (男·新闻)", "zh-CN-XiaoxiaoNeural (女·活泼)", "zh-CN-XiaoyiNeural (女·温和)"],
                "en-US": ["en-US-JennyNeural (女·助手)", "en-US-GuyNeural (男·新闻)", "en-US-AriaNeural (女·专业)"],
            },
            "base_url": "",
            "requires_api_key": False,
        },
        {
            "provider": "doubao",
            "display": "豆包 TTS（火山引擎·高音质）",
            "models": [],
            "voices": {},
            "base_url": "",
            "requires_api_key": True,
        },
        {
            "provider": "openai_tts",
            "display": "OpenAI TTS",
            "models": ["tts-1", "tts-1-hd"],
            "voices": {"default": ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]},
            "base_url": "https://api.openai.com/v1",
            "requires_api_key": True,
        },
    ],
}
