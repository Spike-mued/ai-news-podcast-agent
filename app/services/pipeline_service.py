from __future__ import annotations

from datetime import datetime

import aiosqlite
from langgraph.graph import END, StateGraph
from loguru import logger

from app.agents.base_state import PipelineState
from app.agents.playlist_manager.concatenator import build_playlist
from app.agents.playlist_manager.scheduler import register_trigger_callback
from app.agents.playlist_manager.state import PlaylistManagerState
from app.agents.playlist_manager.stream_manager import manage_stream_queue
from app.agents.podcast_writer.audio_processor import process_audio_segments
from app.agents.podcast_writer.script_writer import write_scripts
from app.agents.podcast_writer.state import PodcastWriterState
from app.agents.podcast_writer.tts_synthesizer import synthesize_audio
from app.config import config
from app.services.news_service import news_collector_graph
from app.services.stream_service import stream_service


async def run_news_collection(state: PipelineState) -> dict:
    """执行新闻采集阶段，调用 news_collector_graph"""
    logger.info("[Pipeline] Phase 1: News Collection")
    sources = state.get("sources", [])
    max_items = state.get("max_items", config.news_max_items)

    result = await news_collector_graph.ainvoke({"sources": sources, "max_items": max_items})

    ranked_news = result.get("final_news", [])
    errors = result.get("fetch_errors", [])

    logger.info(f"[Pipeline] Collected {len(ranked_news)} news items")
    return {
        "raw_news": result.get("raw_news", []),
        "deduplicated_news": result.get("deduplicated_news", []),
        "ranked_news": ranked_news,
        "errors": errors,
    }


async def run_podcast_writing(state: PipelineState) -> dict:
    """执行播客转译阶段"""
    logger.info("[Pipeline] Phase 2: Podcast Writing")
    ranked_news = state.get("ranked_news", [])

    if not ranked_news:
        return {"podcast_scripts": [], "audio_segments": [], "errors": ["No ranked news to write"]}

    # 写脚本
    script_result = await write_scripts({"news_items": ranked_news, "scripts": [], "audio_segments": [], "errors": [], "status": "running"})
    scripts = script_result.get("scripts", [])

    if not scripts:
        return {"podcast_scripts": [], "audio_segments": [], "errors": ["Script generation produced no scripts"]}

    # TTS 合成
    synth_result = await synthesize_audio({"scripts": scripts, "audio_segments": [], "errors": [], "status": "running"})
    audio_segments = synth_result.get("audio_segments", [])

    # 音频后处理
    proc_result = await process_audio_segments({"audio_segments": audio_segments, "errors": [], "status": "running"})
    final_audio = proc_result.get("audio_segments", audio_segments)

    logger.info(f"[Pipeline] Generated {len(final_audio)} audio segments")
    return {
        "podcast_scripts": scripts,
        "audio_segments": final_audio,
        "errors": script_result.get("errors", []) + synth_result.get("errors", []) + proc_result.get("errors", []),
    }


async def run_playlist_building(state: PipelineState) -> dict:
    """执行播单构建阶段"""
    logger.info("[Pipeline] Phase 3: Playlist Building")
    audio_segments = state.get("audio_segments", [])

    if not audio_segments:
        return {"playlist_path": "", "playlist_duration": 0, "errors": ["No audio segments to build playlist"]}

    # 拼接
    concat_result = await build_playlist({"audio_segments": audio_segments, "errors": [], "playlist_path": "", "playlist_duration": 0, "segment_count": 0})
    playlist_path = concat_result.get("playlist_path", "")
    playlist_duration = concat_result.get("playlist_duration", 0)

    if playlist_path:
        stream_service.add_to_queue(playlist_path, playlist_duration)

    return {
        "playlist_path": playlist_path,
        "playlist_duration": playlist_duration,
        "queue_status": "playing" if playlist_path else "empty",
        "errors": concat_result.get("errors", []),
    }


async def _save_pipeline_run(state: PipelineState, status: str = "completed"):
    try:
        db = await aiosqlite.connect(config.database_path)
        await db.execute(
            "INSERT INTO pipeline_runs (status, news_count, podcast_count, completed_at) VALUES (?, ?, ?, datetime('now', 'localtime'))",
            (status, len(state.get("ranked_news", [])), len(state.get("audio_segments", [])),),
        )
        await db.commit()
        await db.close()
    except Exception as e:
        logger.error(f"Failed to save pipeline run: {e}")


def build_pipeline_graph() -> StateGraph:
    """构建主流水线 LangGraph：
    collect → write → playlist → END
    """
    workflow = StateGraph(PipelineState)

    workflow.add_node("collect", run_news_collection)  # type: ignore[arg-type]
    workflow.add_node("write", run_podcast_writing)  # type: ignore[arg-type]
    workflow.add_node("playlist", run_playlist_building)  # type: ignore[arg-type]

    workflow.set_entry_point("collect")
    workflow.add_edge("collect", "write")
    workflow.add_edge("write", "playlist")
    workflow.add_edge("playlist", END)

    return workflow.compile()


pipeline_graph = build_pipeline_graph()


async def run_full_pipeline(sources: list[str] | None = None, max_items: int | None = None, force: bool = False) -> dict:
    """执行完整的新闻播客流水线"""
    logger.info(f"Starting full pipeline (sources={sources}, max_items={max_items})")

    state: PipelineState = {
        "trigger_source": "manual",
        "max_items": max_items or config.news_max_items,
        "raw_news": [],
        "deduplicated_news": [],
        "ranked_news": [],
        "podcast_scripts": [],
        "audio_segments": [],
        "playlist_path": "",
        "playlist_duration": 0,
        "queue_status": "idle",
        "errors": [],
        "warnings": [],
        "sources": sources or [],
    }

    try:
        result = await pipeline_graph.ainvoke(state)
        await _save_pipeline_run(result, "completed")
        logger.info(f"Pipeline completed: {len(result.get('audio_segments', []))} segments")
        return {"success": True, "state": result}
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        await _save_pipeline_run(state, "failed")
        return {"success": False, "error": str(e)}


async def scheduled_pipeline_trigger():
    """定时器触发的流水线执行，也会在队列不足时提前触发"""
    queue_duration = stream_service.queue_duration()
    if queue_duration > 600:
        logger.debug(f"Queue sufficient ({queue_duration:.0f}s), skipping trigger")
        return

    if queue_duration < 300:
        logger.info(f"Queue LOW ({queue_duration:.0f}s) — triggering pipeline early")
    else:
        logger.info("Scheduled pipeline trigger")

    try:
        result = await run_full_pipeline()
        logger.info(f"Scheduled pipeline: {result.get('success')}")
    except Exception as e:
        logger.error(f"Scheduled pipeline failed: {e}")


# 注册定时回调
register_trigger_callback(scheduled_pipeline_trigger)
