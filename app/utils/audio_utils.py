import os
from pathlib import Path

from app.config import config

AUDIO_DIR = Path("data/audio")
EPISODES_DIR = AUDIO_DIR / "episodes"
PLAYLISTS_DIR = AUDIO_DIR / "playlists"
ASSETS_DIR = AUDIO_DIR / "assets"


def ensure_audio_dirs():
    for d in [AUDIO_DIR, EPISODES_DIR, PLAYLISTS_DIR, ASSETS_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def get_episode_path(filename: str) -> str:
    ensure_audio_dirs()
    return str(EPISODES_DIR / filename)


def get_playlist_path(filename: str) -> str:
    ensure_audio_dirs()
    return str(PLAYLISTS_DIR / filename)


def get_asset_path(filename: str) -> str:
    ensure_audio_dirs()
    return str(ASSETS_DIR / filename)


def get_audio_duration_seconds(file_path: str) -> float:
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_file(file_path)
        return len(audio) / 1000.0
    except Exception:
        return 0.0


def validate_audio_file(file_path: str) -> bool:
    if not os.path.exists(file_path):
        return False
    if os.path.getsize(file_path) < 100:
        return False
    return True


def format_duration(seconds: float) -> str:
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}:{secs:02d}"
