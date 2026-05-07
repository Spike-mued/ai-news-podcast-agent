from langgraph.graph import END, StateGraph

from app.agents.playlist_manager.concatenator import build_playlist
from app.agents.playlist_manager.state import PlaylistManagerState
from app.agents.playlist_manager.stream_manager import manage_stream_queue


def build_playlist_manager_graph() -> StateGraph:
    """构建播单管理 LangGraph 子图：
    build_playlist → manage_stream → END
    """
    workflow = StateGraph(PlaylistManagerState)

    workflow.add_node("build_playlist", build_playlist)  # type: ignore[arg-type]
    workflow.add_node("manage_stream", manage_stream_queue)  # type: ignore[arg-type]

    workflow.set_entry_point("build_playlist")
    workflow.add_edge("build_playlist", "manage_stream")
    workflow.add_edge("manage_stream", END)

    return workflow.compile()


playlist_manager_graph = build_playlist_manager_graph()
