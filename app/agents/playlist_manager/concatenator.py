from datetime import datetime

import aiosqlite
from loguru import logger

from app.agents.playlist_manager.state import PlaylistManagerState
from app.config import config
from app.services.audio_service import audio_service


async def build_playlist(state: PlaylistManagerState) -> dict:
    """将音频片段拼接为完整播单音频文件"""
    audio_segments = state.get("audio_segments", [])
    if not audio_segments:
        logger.warning("No audio segments to concatenate")
        return {"playlist_path": "", "playlist_duration": 0.0, "segment_count": 0}

    # 按重要性排序
    sorted_segments = sorted(audio_segments, key=lambda x: x.get("importance_score", 0), reverse=True)

    audio_files = [seg.get("audio_path", "") for seg in sorted_segments if seg.get("audio_path")]
    audio_files = [f for f in audio_files if f]

    if not audio_files:
        return {"playlist_path": "", "playlist_duration": 0.0, "segment_count": 0, "errors": ["No valid audio files"]}

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"playlist_{timestamp}.mp3"
    output_path = audio_service.concatenate(audio_files, output_filename)
    duration = audio_service.get_duration(output_path)

    # 保存播单到数据库
    await _save_playlist_to_db(sorted_segments, output_path, duration, timestamp)

    logger.info(f"Playlist built: {output_filename} ({duration:.1f}s, {len(audio_files)} segments)")
    return {
        "playlist_path": output_path,
        "playlist_duration": duration,
        "segment_count": len(audio_files),
    }


async def _save_playlist_to_db(segments: list[dict], audio_path: str, duration: float, timestamp: str):
    try:
        db = await aiosqlite.connect(config.database_path)
        db.row_factory = aiosqlite.Row

        # 获取已保存的 podcast IDs
        podcast_ids: list[int] = []
        for seg in segments:
            news_url = seg.get("news_url", "")
            cursor = await db.execute("SELECT id FROM podcasts WHERE title = ? ORDER BY id DESC LIMIT 1", (seg.get("title", ""),))
            row = await cursor.fetchone()
            if row:
                podcast_ids.append(row["id"])
            else:
                cursor = await db.execute(
                    """INSERT INTO podcasts (news_id, title, script, audio_path, audio_duration, importance_level, status, completed_at)
                       VALUES (0, ?, ?, ?, ?, ?, 'completed', datetime('now', 'localtime'))""",
                    (
                        seg.get("title", ""),
                        seg.get("script", ""),
                        seg.get("audio_path", ""),
                        seg.get("audio_duration", 0),
                        seg.get("importance_score", 5),
                    ),
                )
                await db.commit()
                podcast_ids.append(cursor.lastrowid)

        podcast_ids_json = "[" + ",".join(str(pid) for pid in podcast_ids) + "]"
        name = f"Playlist_{timestamp}"
        await db.execute(
            "INSERT INTO playlists (name, podcast_ids, audio_path, total_duration, status, completed_at) VALUES (?, ?, ?, ?, 'completed', datetime('now', 'localtime'))",
            (name, podcast_ids_json, audio_path, duration),
        )
        await db.commit()
        await db.close()
    except Exception as e:
        logger.error(f"Failed to save playlist to DB: {e}")
