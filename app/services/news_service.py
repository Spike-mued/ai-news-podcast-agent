from langgraph.graph import END, StateGraph

from app.agents.news_collector.collector import collect_news
from app.agents.news_collector.deduplicator import deduplicate_news
from app.agents.news_collector.ranker import rank_news
from app.agents.news_collector.state import NewsCollectorState


def build_news_collector_graph() -> StateGraph:
    """构建新闻采集 LangGraph 子图：
    collect → deduplicate → rank → END
    """
    workflow = StateGraph(NewsCollectorState)

    workflow.add_node("collect", collect_news)  # type: ignore[arg-type]
    workflow.add_node("deduplicate", deduplicate_news)  # type: ignore[arg-type]
    workflow.add_node("rank", rank_news)  # type: ignore[arg-type]

    workflow.set_entry_point("collect")
    workflow.add_edge("collect", "deduplicate")
    workflow.add_edge("deduplicate", "rank")
    workflow.add_edge("rank", END)

    return workflow.compile()


news_collector_graph = build_news_collector_graph()
