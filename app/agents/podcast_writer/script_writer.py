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


def _generate_fallback_script(title: str, source: str, score: int) -> str:
    """当 LLM 不可用时，生成足够长的 fallback 播客脚本（约 200-400 字，1-2 分钟）"""
    if score >= 7:
        template = (
            f"嘿，大家好！今天有一条重磅消息要和大家聊聊。这条新闻来自{source}，说的是：{title}。"
            f"这条消息之所以重要，是因为它对整个AI行业都有深远的影响。我们来仔细分析一下，"
            f"首先从技术角度来看，这代表了行业的一个重要突破。不仅展示了技术的前沿方向，"
            f"更可能改变我们未来使用AI的方式。其次从产业层面来说，这个消息可能会影响"
            f"从芯片到应用层的整个产业链。对于开发者来说，这意味着新的工具和机会；"
            f"对于普通用户来说，这意味着更智能的产品体验。说实话，看到这个消息的时候，"
            f"我个人是非常兴奋的。因为这意味着AI技术又向前迈进了一大步。"
            f"我们会持续关注这个方向的最新动态，第一时间带来深度解读。"
            f"好了，这就是今天要和大家分享的重磅消息，我们下一条新闻见。"
        )
    elif score >= 5:
        template = (
            f"来关注一条来自{source}的消息：{title}。这条新闻挺有意思的，"
            f"对AI行业来说值得关注。简单说一下背景，最近行业内类似的消息不少，"
            f"但这一条有其独特之处。它反映了当前技术发展的一个新趋势，"
            f"对于关注AI的朋友来说是不容错过的信息。从实际应用角度看，"
            f"这个消息可能会带来一些有意思的变化。无论是对于开发者还是用户，"
            f"都值得保持关注。我们也会继续跟踪后续进展，有新消息第一时间告诉大家。"
            f"好了，说完这条，我们接着往下看。"
        )
    else:
        template = (
            f"快速播报一条来自{source}的资讯：{title}。"
            f"简短来说，这是AI领域的一个新动向，虽然可能不是最重磅的消息，"
            f"但对于关注行业动态的朋友来说也值得一看。科技发展日新月异，"
            f"每一条新闻背后都反映着行业的脉动。好了，这条就到这里。"
        )
    return template


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
            script_text = _generate_fallback_script(title, source, score)

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
