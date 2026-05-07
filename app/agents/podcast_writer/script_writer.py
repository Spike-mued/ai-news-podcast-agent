import json

from loguru import logger

from app.agents.podcast_writer.state import PodcastWriterState
from app.core.constants import IMPORTANCE_CRITICAL, IMPORTANCE_HIGH, IMPORTANCE_MEDIUM
from app.core.llm_factory import llm_factory


BATCH_SCRIPT_PROMPT = """你是一个AI科技播客的主播，风格轻松幽默，像一个懂技术的朋友在聊天。

下面是一组今天要播报的AI/科技新闻，请你将它们写成一篇连贯的口播稿。

## 规则
1. 输出一个JSON数组，数组中每个元素是一条新闻的口播脚本
2. 每条脚本之间要有自然的过渡（"接下来看看..."、"还有一个重磅消息..."、"说到这个，我想起..."等）
3. 第一条脚本要包含开场白（"嘿大家好，欢迎收听AI新闻播客..."）
4. 最后一条脚本要包含结束语（"好了，以上就是今天的AI新闻简报，我们下次再见！"）
5. 中间每条脚本的结尾要自然地引出下一条

## 脚本长度（每条）
- 重要性9-10分：400-600字（深度解读，2-3分钟）
- 重要性7-8分：200-400字（标准报道，1-2分钟）
- 重要性4-6分：100-200字（简要播报，30-60秒）

## 风格
- 中文为主，技术术语保留英文
- 口语化，像朋友聊天不是新闻联播
- 适当加入「说实话」「有意思的是」「大家猜怎么着」等口语

## 新闻列表
{news_json}

请直接返回JSON数组，格式：[{{"url": "...", "script": "..."}}, ...]，不要加任何其他文字。"""


FALLBACK_TRANSITIONS = [
    "接下来看看另一条消息。",
    "还有一个值得关注的新闻。",
    "再来看一条有意思的消息。",
    "下面这条也很重要。",
    "接着往下看。",
    "说完这个，再看看另一个消息。",
]


def _generate_batch_fallback(news_items: list[dict]) -> list[dict]:
    """当 LLM 不可用时，生成连贯的 fallback 脚本"""
    scripts: list[dict] = []
    total = len(news_items)

    for i, item in enumerate(news_items):
        title = item.get("title", "Unknown")
        source = item.get("source", "Unknown")
        score = item.get("importance_score", 5)

        # 根据位置添加过渡
        prefix = ""
        suffix = ""
        if i == 0:
            prefix = "嘿大家好，欢迎收听AI新闻播客。今天的第一条新闻："
        elif i < total - 1:
            from random import choice
            prefix = choice(FALLBACK_TRANSITIONS)
        else:
            prefix = "最后一条新闻："

        if i == total - 1:
            suffix = "好了，以上就是今天的AI新闻简报，我们下期再见！"

        if score >= 7:
            body = (
                f"{title}。这条消息来自{source}，分量很重。"
                f"它反映了当前AI行业的一个重要趋势，对技术发展有深远影响。"
                f"从应用角度看，这个消息可能会带来新的产品形态和用户体验升级。"
                f"行业内的关注度很高，值得持续跟踪后续进展。"
            )
        elif score >= 5:
            body = (
                f"{title}。来自{source}的报道。"
                f"这条新闻对关注AI的朋友来说值得留意，"
                f"反映了行业正在发生的一些变化。"
            )
        else:
            body = f"{title}。简短播报一下，来自{source}。对行业也是一个信号。"

        script_text = f"{prefix}{body}{suffix}"
        scripts.append({
            "news_url": item.get("url", ""),
            "title": title,
            "source": source,
            "importance_score": score,
            "script": script_text,
            "language": item.get("language", "zh"),
            "is_first": i == 0,
            "is_last": i == total - 1,
        })

    return scripts


async def write_scripts_batch(news_items: list[dict]) -> list[dict]:
    """尝试批量生成连贯脚本，失败则回退到逐条 fallback"""
    if not news_items:
        return []

    news_for_llm = [
        {
            "index": i,
            "title": item.get("title", ""),
            "source": item.get("source", ""),
            "score": item.get("importance_score", 5),
            "url": item.get("url", ""),
        }
        for i, item in enumerate(news_items)
    ]
    news_json = json.dumps(news_for_llm, ensure_ascii=False, indent=2)

    try:
        llm = llm_factory.create_chat_model(temperature=0.8, streaming=False)
        response = await llm.ainvoke(BATCH_SCRIPT_PROMPT.format(news_json=news_json))
        content = response.content if hasattr(response, "content") else str(response)
        content = content.strip()
        if content.startswith("```"):
            start = content.index("[")
            end = content.rindex("]") + 1
            content = content[start:end]
        llm_scripts = json.loads(content)
    except Exception as e:
        logger.warning(f"Batch script generation failed: {e}, using fallback")
        return _generate_batch_fallback(news_items)

    # 合并 LLM 生成的脚本与原始新闻数据
    scripts: list[dict] = []
    for i, item in enumerate(news_items):
        llm_script = llm_scripts[i] if i < len(llm_scripts) else {}
        scripts.append({
            "news_url": item.get("url", ""),
            "title": item.get("title", ""),
            "source": item.get("source", ""),
            "importance_score": item.get("importance_score", 5),
            "script": llm_script.get("script", _quick_fallback(item)),
            "language": item.get("language", "zh"),
            "is_first": i == 0,
            "is_last": i == len(news_items) - 1,
        })

    return scripts


def _quick_fallback(item: dict) -> str:
    title = item.get("title", "")
    source = item.get("source", "")
    return f"来自{source}的消息：{title}。我们来关注一下这个新闻。"


async def write_scripts(state: PodcastWriterState) -> dict:
    """为所有新闻生成连贯的播客脚本"""
    news_items = state.get("news_items", [])
    if not news_items:
        logger.warning("No news items to write scripts for")
        return {"scripts": [], "status": "completed"}

    try:
        scripts = await write_scripts_batch(news_items)
    except Exception as e:
        logger.error(f"Script generation completely failed: {e}")
        scripts = _generate_batch_fallback(news_items)

    total_chars = sum(len(s["script"]) for s in scripts)
    logger.info(f"Generated {len(scripts)} scripts, total {total_chars} chars")
    return {"scripts": scripts, "errors": [], "status": "completed"}
