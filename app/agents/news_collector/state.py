import operator
from typing import Annotated, TypedDict


class NewsCollectorState(TypedDict):
    """新闻采集 Agent 状态"""

    # 输入配置
    sources: list[str]
    max_items: int

    # 采集阶段
    raw_news: Annotated[list[dict], operator.add]
    fetch_errors: Annotated[list[str], operator.add]

    # 去重阶段
    deduplicated_news: list[dict]

    # 排序阶段
    ranked_news: list[dict]

    # 最终输出
    final_news: list[dict]
    pipeline_status: str
