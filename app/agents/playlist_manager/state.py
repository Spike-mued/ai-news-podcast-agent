import operator
from typing import Annotated, TypedDict


class PlaylistManagerState(TypedDict):
    """播单管理器 Agent 状态"""

    # 输入
    audio_segments: list[dict]

    # 拼接阶段
    playlist_path: str
    playlist_duration: float
    segment_count: int

    # 调度阶段
    next_trigger_time: str
    queue_length: int

    # 流媒体阶段
    stream_status: str
    current_position: float

    # 错误
    errors: Annotated[list[str], operator.add]
