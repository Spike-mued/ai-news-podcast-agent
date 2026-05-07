import json

from loguru import logger

from app.agents.podcast_writer.state import PodcastWriterState
from app.core.constants import IMPORTANCE_CRITICAL, IMPORTANCE_HIGH, IMPORTANCE_MEDIUM
from app.core.llm_factory import llm_factory


SCRIPT_PROMPT = """你是一个AI科技播客的主播，风格轻松幽默，像一个懂技术的朋友在聊天。请将以下AI新闻转写成口语化的播客脚本。

## 新闻信息
- 标题：{title}
- 来源：{source}
- 重要性评分：{score}/10

## 脚本长度要求
{length_requirement}

## 风格指南
- 中文为主，关键技术术语保留英文
- 开场用「嘿，大家好」或类似的轻松开场
- 加入自然的过渡词（"接下来看看"、"还有一个有意思的消息"）
- 结尾可以用简短的总结或评论
- 可以适当加入「嗯」「说实话」「你猜怎么着」等口语化表达
- 读起来像朋友在聊天，不是新闻联播

请直接输出播客脚本，不要加任何标记。"""

LENGTH_REQUIREMENTS = {
    "critical": "深度解读模式：2-3分钟的脚本（约400-600字），包含背景分析、技术细节、行业影响",
    "high": "标准报道模式：1-2分钟的脚本（约200-400字），清晰介绍新闻要点和影响",
    "medium": "简要提及模式：30秒-1分钟的脚本（约100-200字），快速带过核心信息",
    "low": "一句话带过：30秒以内（约50-100字）",
}


def _get_length_requirement(score: int) -> str:
    if IMPORTANCE_CRITICAL[0] <= score <= IMPORTANCE_CRITICAL[1]:
        return LENGTH_REQUIREMENTS["critical"]
    elif IMPORTANCE_HIGH[0] <= score <= IMPORTANCE_HIGH[1]:
        return LENGTH_REQUIREMENTS["high"]
    elif IMPORTANCE_MEDIUM[0] <= score <= IMPORTANCE_MEDIUM[1]:
        return LENGTH_REQUIREMENTS["medium"]
    return LENGTH_REQUIREMENTS["low"]


async def write_scripts(state: PodcastWriterState) -> dict:
    """为每条新闻生成播客脚本"""
    news_items = state.get("news_items", [])
    if not news_items:
        logger.warning("No news items to write scripts for")
        return {"scripts": [], "status": "completed"}

    scripts: list[dict] = []
    errors: list[str] = []

    for i, item in enumerate(news_items):
        title = item.get("title", "Unknown")
        source = item.get("source", "Unknown")
        score = item.get("importance_score", 5)

        length_req = _get_length_requirement(score)

        try:
            llm = llm_factory.create_chat_model(temperature=0.8, streaming=False)
            prompt = SCRIPT_PROMPT.format(title=title, source=source, score=score, length_requirement=length_req)
            response = await llm.ainvoke(prompt)
            script_text = response.content if hasattr(response, "content") else str(response)
            script_text = script_text.strip()
        except Exception as e:
            logger.error(f"Script generation failed for '{title}': {e}")
            errors.append(f"Script failed: {title}")
            script_text = f"接下来是一条关于AI的新闻：{title}。详情请查看原文链接。"

        scripts.append(
            {
                "news_url": item.get("url", ""),
                "title": title,
                "source": source,
                "importance_score": score,
                "script": script_text,
                "language": item.get("language", "zh"),
            }
        )
        logger.info(f"Script [{i + 1}/{len(news_items)}]: {title[:40]}... ({len(script_text)} chars)")

    logger.info(f"Generated {len(scripts)} scripts, {len(errors)} errors")
    return {"scripts": scripts, "errors": errors, "status": "completed"}
