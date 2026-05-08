import operator
from typing import Annotated, TypedDict


class PodcastWriterState(TypedDict):
    """播客转译 Agent 状态（TTS + 音频处理）"""

    # 输入：来自 Script Writer Agent
    scripts: list[dict]

    # TTS 合成阶段
    audio_segments: Annotated[list[dict], operator.add]

    # 错误收集
    errors: Annotated[list[str], operator.add]

    # 状态
    status: str
