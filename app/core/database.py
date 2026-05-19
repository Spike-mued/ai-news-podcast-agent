import aiosqlite
from pathlib import Path

from app.config import config
from loguru import logger


CREATE_NEWS_SOURCES_TABLE = """
CREATE TABLE IF NOT EXISTS news_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    type TEXT NOT NULL DEFAULT 'rss',
    url TEXT NOT NULL,
    language TEXT DEFAULT 'zh',
    priority INTEGER DEFAULT 5,
    is_enabled INTEGER DEFAULT 1,
    keywords TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
"""

CREATE_NEWS_TABLE = """
CREATE TABLE IF NOT EXISTS news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    summary TEXT,
    url TEXT UNIQUE NOT NULL,
    source TEXT NOT NULL,
    source_type TEXT DEFAULT 'rss',
    published_at TEXT,
    importance_score INTEGER DEFAULT 0,
    importance_reason TEXT,
    content_hash TEXT,
    language TEXT DEFAULT 'zh',
    raw_data TEXT,
    collected_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    is_used INTEGER DEFAULT 0,
    is_archived INTEGER DEFAULT 0
);
"""

CREATE_PODCAST_TABLE = """
CREATE TABLE IF NOT EXISTS podcasts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    news_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    script TEXT NOT NULL,
    audio_path TEXT,
    audio_duration REAL DEFAULT 0,
    importance_level INTEGER DEFAULT 5,
    status TEXT DEFAULT 'pending',
    error_message TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    completed_at TEXT,
    is_archived INTEGER DEFAULT 0,
    FOREIGN KEY (news_id) REFERENCES news(id)
);
"""

CREATE_PLAYLIST_TABLE = """
CREATE TABLE IF NOT EXISTS playlists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    podcast_ids TEXT NOT NULL,
    audio_path TEXT,
    total_duration REAL DEFAULT 0,
    status TEXT DEFAULT 'building',
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    completed_at TEXT
);
"""

CREATE_PIPELINE_RUNS_TABLE = """
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    status TEXT NOT NULL DEFAULT 'running',
    news_count INTEGER DEFAULT 0,
    podcast_count INTEGER DEFAULT 0,
    playlist_id INTEGER,
    error_message TEXT,
    started_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    completed_at TEXT,
    FOREIGN KEY (playlist_id) REFERENCES playlists(id)
);
"""

CREATE_MODEL_CONNECTIONS_TABLE = """
CREATE TABLE IF NOT EXISTS model_connections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    service_type TEXT NOT NULL CHECK(service_type IN ('llm','tts')),
    provider TEXT NOT NULL,
    base_url TEXT DEFAULT '',
    api_key TEXT DEFAULT '',
    model TEXT DEFAULT '',
    voice TEXT DEFAULT '',
    extra_config TEXT DEFAULT '{}',
    is_active INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
"""

CREATE_NEWS_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_news_url ON news(url);",
    "CREATE INDEX IF NOT EXISTS idx_news_source ON news(source);",
    "CREATE INDEX IF NOT EXISTS idx_news_published ON news(published_at);",
    "CREATE INDEX IF NOT EXISTS idx_news_score ON news(importance_score);",
    "CREATE INDEX IF NOT EXISTS idx_news_hash ON news(content_hash);",
]

CREATE_PODCAST_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_podcast_news_id ON podcasts(news_id);",
    "CREATE INDEX IF NOT EXISTS idx_podcast_status ON podcasts(status);",
]

ARCHIVE_MIGRATIONS = [
    "ALTER TABLE news ADD COLUMN is_archived INTEGER DEFAULT 0",
    "ALTER TABLE podcasts ADD COLUMN is_archived INTEGER DEFAULT 0",
]


async def _seed_sources_from_yaml(db: aiosqlite.Connection):
    """首次启动时从 YAML 导入预设新闻源到数据库"""
    yaml_path = Path("config/news_sources.yaml")
    if not yaml_path.exists():
        return
    import yaml
    with open(yaml_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    for src in cfg.get("sources", []):
        await db.execute(
            "INSERT OR IGNORE INTO news_sources (name, type, url, language, priority) VALUES (?, ?, ?, ?, ?)",
            (src.get("name", ""), src.get("type", "rss"), src.get("url", ""), src.get("language", "zh"), src.get("priority", 5)),
        )
    await db.commit()
    logger.info(f"Seeded {len(cfg.get('sources', []))} sources from YAML")


async def _seed_model_connections(db: aiosqlite.Connection):
    """首次启动时从 .env 导入默认模型连接"""
    from app.config import config

    defaults = [
        ("DashScope 通义千问 (.env)", "llm", "dashscope", config.dashscope_api_base, config.dashscope_api_key, config.dashscope_model, "", 1),
        ("Edge TTS 中文 (.env)", "tts", "edge_tts", "", "", "", config.tts_voice_zh, 1),
    ]
    for name, svc, prov, url, key, model, voice, active in defaults:
        await db.execute(
            "INSERT OR IGNORE INTO model_connections (name, service_type, provider, base_url, api_key, model, voice, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (name, svc, prov, url, key, model, voice, active),
        )
    await db.commit()
    logger.info(f"Seeded {len(defaults)} default model connections from .env")


async def init_database() -> aiosqlite.Connection:
    db = await aiosqlite.connect(config.database_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")

    await db.execute(CREATE_NEWS_SOURCES_TABLE)
    await db.execute(CREATE_NEWS_TABLE)
    await db.execute(CREATE_PODCAST_TABLE)
    await db.execute(CREATE_PLAYLIST_TABLE)
    await db.execute(CREATE_PIPELINE_RUNS_TABLE)
    await db.execute(CREATE_MODEL_CONNECTIONS_TABLE)

    for idx_sql in CREATE_NEWS_INDEXES + CREATE_PODCAST_INDEXES:
        await db.execute(idx_sql)

    await db.commit()

    # 迁移：为旧数据库添加 is_archived 列（忽略已存在的错误）
    for sql in ARCHIVE_MIGRATIONS:
        try:
            await db.execute(sql)
        except Exception:
            pass
    await db.commit()

    # 从 YAML 种子数据
    cursor = await db.execute("SELECT COUNT(*) FROM news_sources")
    count = (await cursor.fetchone())[0]
    if count == 0:
        await _seed_sources_from_yaml(db)

    # 种子默认模型连接（从 .env）
    cursor = await db.execute("SELECT COUNT(*) FROM model_connections")
    count = (await cursor.fetchone())[0]
    if count == 0:
        await _seed_model_connections(db)

    logger.info("Database initialized successfully")
    return db


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(config.database_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys=ON")
    return db
