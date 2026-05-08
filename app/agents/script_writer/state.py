import operator
from typing import Annotated, TypedDict


class ScriptWriterState(TypedDict):
    """脚本撰写 Agent 状态"""

    # 输入
    news_items: list[dict]

    # 输出
    scripts: Annotated[list[dict], operator.add]

    # 状态和错误
    status: str
    errors: Annotated[list[str], operator.add]
