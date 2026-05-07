import aiosqlite

from app.config import config
from loguru import logger


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
    is_used INTEGER DEFAULT 0
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


async def init_database() -> aiosqlite.Connection:
    db = await aiosqlite.connect(config.database_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")

    await db.execute(CREATE_NEWS_TABLE)
    await db.execute(CREATE_PODCAST_TABLE)
    await db.execute(CREATE_PLAYLIST_TABLE)
    await db.execute(CREATE_PIPELINE_RUNS_TABLE)

    for idx_sql in CREATE_NEWS_INDEXES + CREATE_PODCAST_INDEXES:
        await db.execute(idx_sql)

    await db.commit()
    logger.info("Database initialized successfully")
    return db


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(config.database_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys=ON")
    return db
