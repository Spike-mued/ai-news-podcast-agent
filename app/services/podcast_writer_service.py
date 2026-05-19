from langgraph.graph import END, StateGraph

from app.agents.podcast_writer.audio_processor import process_audio_segments
from app.agents.podcast_writer.state import PodcastWriterState
from app.agents.podcast_writer.tts_synthesizer import synthesize_audio


def build_podcast_writer_graph() -> StateGraph:
    """构建播客转译 LangGraph 子图：
    synthesize_audio → process_audio → END
    """
    workflow = StateGraph(PodcastWriterState)

    workflow.add_node("synthesize", synthesize_audio)  # type: ignore[arg-type]
    workflow.add_node("process_audio", process_audio_segments)  # type: ignore[arg-type]

    workflow.set_entry_point("synthesize")
    workflow.add_edge("synthesize", "process_audio")
    workflow.add_edge("process_audio", END)

    return workflow.compile()


podcast_writer_graph = build_podcast_writer_graph()
