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

    # TTS
    tts_voice: str = "zh-CN-XiaoxiaoNeural"
    tts_rate: str = "+10%"
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
