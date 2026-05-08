from __future__ import annotations

from datetime import datetime

import aiosqlite
from langgraph.graph import END, StateGraph
from loguru import logger

from app.agents.base_state import PipelineState
from app.agents.playlist_manager.concatenator import build_playlist
from app.agents.playlist_manager.scheduler import register_trigger_callback
from app.agents.podcast_writer.audio_processor import process_audio_segments
from app.agents.podcast_writer.tts_synthesizer import synthesize_audio
from app.agents.script_writer.writer import write_scripts_node
from app.config import config
from app.services.news_service import news_collector_graph
from app.services.stream_service import stream_service


# ============================================================
# Phase 1: News Collection
# ============================================================
async def run_news_collection(state: PipelineState) -> dict:
    logger.info("[Phase 1] News Collection")
    sources = state.get("sources", [])
    max_items = state.get("max_items", config.news_max_items)
    result = await news_collector_graph.ainvoke({"sources": sources, "max_items": max_items})
    ranked_news = result.get("final_news", [])
    logger.info(f"[Phase 1] Collected {len(ranked_news)} news items")
    return {
        "raw_news": result.get("raw_news", []),
        "deduplicated_news": result.get("deduplicated_news", []),
        "ranked_news": ranked_news,
        "errors": result.get("fetch_errors", []),
    }


# ============================================================
# Phase 2: Script Writing (NEW — standalone agent)
# ============================================================
async def run_script_writing(state: PipelineState) -> dict:
    logger.info("[Phase 2] Script Writing")
    ranked_news = state.get("ranked_news", [])
    if not ranked_news:
        return {"scripts": [], "errors": ["No ranked news to write scripts for"]}

    result = await write_scripts_node({"news_items": ranked_news, "scripts": [], "status": "running", "errors": []})
    scripts = result.get("scripts", [])
    logger.info(f"[Phase 2] Generated {len(scripts)} scripts")
    return {"scripts": scripts, "errors": result.get("errors", [])}


# ============================================================
# Phase 3: TTS Synthesis + Audio Processing
# ============================================================
async def run_tts_synthesis(state: PipelineState) -> dict:
    logger.info("[Phase 3] TTS Synthesis")
    scripts = state.get("scripts", [])
    if not scripts:
        return {"audio_segments": [], "errors": ["No scripts to synthesize"]}

    synth_result = await synthesize_audio({"scripts": scripts, "audio_segments": [], "errors": [], "status": "running"})
    audio_segments = synth_result.get("audio_segments", [])

    proc_result = await process_audio_segments({"audio_segments": audio_segments, "errors": [], "status": "running"})
    final_audio = proc_result.get("audio_segments", audio_segments)

    logger.info(f"[Phase 3] Synthesized {len(final_audio)} audio segments")
    return {
        "audio_segments": final_audio,
        "errors": synth_result.get("errors", []) + proc_result.get("errors", []),
    }


# ============================================================
# Phase 4: Playlist Building + Streaming
# ============================================================
async def run_playlist_building(state: PipelineState) -> dict:
    logger.info("[Phase 4] Playlist Building")
    audio_segments = state.get("audio_segments", [])
    if not audio_segments:
        return {"playlist_path": "", "playlist_duration": 0, "errors": ["No audio to build playlist"]}

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


# ============================================================
# Graph & Entry Points
# ============================================================
def _save_pipeline_run(state: PipelineState, status: str):
    """非阻塞保存流水线运行记录"""
    import asyncio
    async def _save():
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
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_save())
    except RuntimeError:
        pass


def build_pipeline_graph() -> StateGraph:
    """构建 4 阶段主流水线：
    collect → write_scripts → tts → playlist → END
    """
    workflow = StateGraph(PipelineState)

    workflow.add_node("collect", run_news_collection)      # type: ignore[arg-type]
    workflow.add_node("write_scripts", run_script_writing)  # type: ignore[arg-type]
    workflow.add_node("tts", run_tts_synthesis)             # type: ignore[arg-type]
    workflow.add_node("playlist", run_playlist_building)    # type: ignore[arg-type]

    workflow.set_entry_point("collect")
    workflow.add_edge("collect", "write_scripts")
    workflow.add_edge("write_scripts", "tts")
    workflow.add_edge("tts", "playlist")
    workflow.add_edge("playlist", END)

    return workflow.compile()


pipeline_graph = build_pipeline_graph()


async def run_full_pipeline(sources: list[str] | None = None, max_items: int | None = None, force: bool = False) -> dict:
    logger.info(f"Starting 4-phase pipeline (sources={sources}, max_items={max_items})")

    state: PipelineState = {
        "trigger_source": "manual",
        "max_items": max_items or config.news_max_items,
        "raw_news": [],
        "deduplicated_news": [],
        "ranked_news": [],
        "scripts": [],
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
        _save_pipeline_run(result, "completed")
        logger.info(f"Pipeline completed: {len(result.get('audio_segments', []))} segments")
        return {"success": True, "state": result}
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        _save_pipeline_run(state, "failed")
        return {"success": False, "error": str(e)}


async def scheduled_pipeline_trigger():
    queue_duration = stream_service.queue_duration()
    if queue_duration > 600:
        logger.debug(f"Queue sufficient ({queue_duration:.0f}s), skipping")
        return
    if queue_duration < 300:
        logger.info(f"Queue LOW ({queue_duration:.0f}s) — early trigger")
    else:
        logger.info("Scheduled pipeline trigger")
    try:
        result = await run_full_pipeline()
        logger.info(f"Scheduled pipeline: {result.get('success')}")
    except Exception as e:
        logger.error(f"Scheduled pipeline failed: {e}")


register_trigger_callback(scheduled_pipeline_trigger)
