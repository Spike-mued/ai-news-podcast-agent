import operator
from typing import Annotated, TypedDict


class PodcastWriterState(TypedDict):
    """播客转译 Agent 状态"""

    # 输入
    news_items: list[dict]

    # 脚本生成阶段
    scripts: Annotated[list[dict], operator.add]

    # TTS 合成阶段
    audio_segments: Annotated[list[dict], operator.add]

    # 错误收集
    errors: Annotated[list[str], operator.add]

    # 状态
    status: str
