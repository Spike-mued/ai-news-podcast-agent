from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "AI-News-Podcast-Agent"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 9800

    # DashScope
    dashscope_api_key: str = ""
    dashscope_model: str = "qwen-plus"
    dashscope_api_base: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # News Collection
    news_collection_interval_minutes: int = 30
    news_max_items: int = 15
    news_importance_threshold: int = 4
    news_keywords: str = ""
    news_keywords_mode: str = "boost"

    # TTS
    tts_voice_zh: str = "zh-CN-YunxiNeural"
    tts_voice_en: str = "en-US-JennyNeural"
    tts_rate_slow: str = "-5%"
    tts_rate_normal: str = "+5%"
    tts_rate_fast: str = "+15%"
    tts_pitch: str = "+0Hz"
    tts_volume: str = "+0%"

    # Audio
    audio_sample_rate: int = 24000
    audio_format: str = "mp3"
    audio_segment_max_duration: int = 180

    # Stream
    stream_buffer_size: int = 4096
    stream_bitrate: str = "128k"

    # Database
    database_path: str = "data/podcast.db"


config = Settings()
