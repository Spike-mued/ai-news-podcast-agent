import operator
from typing import Annotated, TypedDict


class PipelineState(TypedDict):
    """主流水线共享状态，使用 operator.add 实现 append-only 字段"""

    # 输入
    trigger_source: str
    max_items: int

    # 新闻采集阶段
    raw_news: Annotated[list[dict], operator.add]
    deduplicated_news: list[dict]
    ranked_news: list[dict]

    # 播客转译阶段
    podcast_scripts: Annotated[list[dict], operator.add]
    audio_segments: Annotated[list[dict], operator.add]

    # 播单管理阶段
    playlist_path: str
    playlist_duration: float
    queue_status: str

    # 错误收集
    errors: Annotated[list[str], operator.add]
    warnings: Annotated[list[str], operator.add]
