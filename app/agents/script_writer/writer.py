from __future__ import annotations

import json
from random import choice

from loguru import logger

from app.agents.script_writer.state import ScriptWriterState
from app.core.llm_factory import llm_factory


BATCH_SCRIPT_PROMPT = """你是一个24小时不间断AI新闻播客的主播，风格轻松自然。

下面是一组今天要播报的AI/科技新闻，按重要性排序。请为每条新闻撰写播客脚本。

## 核心规则
- **每条脚本至少250字**（约1-2分钟口播），确保有足够深度
- 每条脚本之间自然过渡，引出下一条新闻
- 过渡示例："说到AI，还有一个消息..."、"紧接着来看看..."、"同样值得关注的是..."
- **不要有任何结束语！** 不要说"下期再见"、"以上就是今天"等 — 因为播客24小时不间断
- 第一条也不需要开场白，直接进入主题，像一直在播的电台一样自然接续

## 脚本长度
- 重要性9-10分：400-600字（深度解读）
- 重要性7-8分：300-400字
- 重要性4-6分：200-300字

## 风格
- 中文为主，技术术语保留英文
- 口语化，朋友聊天风格
- 适当加入"说实话""有意思的是""大家猜怎么着"等口语

{rag_context}

## 新闻列表（按重要性排序）
{news_json}

请严格返回JSON数组：[{{"url": "...", "script": "..."}}, ...]，不要其他任何文字。"""


FALLBACK_TRANSITIONS = [
    "说到AI领域，再来看另一个消息。",
    "紧接着来看看下一条新闻。",
    "同样值得关注的还有这个消息。",
    "换个角度，再来看一条相关新闻。",
    "接下来这条也很有意思。",
    "另外一边，还有一条消息值得关注。",
    "再说说另一个方向的发展。",
]


def _build_rag_context(related_news: list[dict]) -> str:
    """从历史新闻构建 RAG 上下文"""
    if not related_news:
        return ""
    lines = ["## 近期已播报的相关新闻（避免重复，可引用）"]
    for n in related_news[:5]:
        lines.append(f"- [{n.get('source','')}] {n.get('title','')} (评分{n.get('importance_score',0)})")
    return "\n".join(lines) + "\n"


def _fallback_zh_high(title: str, source: str, score: int, history_ref: str) -> str:
    """高分中文新闻：400-500 字 ≈ 2分钟口播"""
    return (
        f"先来看看这条重磅消息：{title}。这条新闻来自{source}，分量非常重，我们来仔细聊一聊。"
        f"首先从技术角度看，这确实代表了一个重要的行业突破。它不只是一个概念验证，"
        f"而是真正有可能改变现有技术格局的东西。我们来想一下它的影响——"
        f"对于开发者来说，这意味着新的工具链、新的API、新的工作方式。"
        f"对于企业来说，这可能带来效率上的质的飞跃，甚至改变整个业务流程。"
        f"对于普通用户来说，体验上的提升会非常明显，虽然你可能感觉不到底层技术的变化，"
        f"但产品的智能化程度会大大提高。"
        f"{history_ref}"
        f"从整个行业生态来看，这类消息的密集出现说明AI技术正在加速落地，"
        f"不再是纸上谈兵。技术成熟度、商业可行性、用户接受度，这三个维度都在同步推进。"
        f"我们会持续跟踪这个方向的后续进展，有新消息第一时间在这里更新。"
        f"说实话，看到这样的消息，我个人是非常兴奋的。"
        f"因为它意味着人工智能又向前迈进了一大步，而这还只是一个开始。"
    )


def _fallback_zh_mid(title: str, source: str, score: int, history_ref: str) -> str:
    """中等中文新闻：300-350 字 ≈ 1.5分钟口播"""
    return (
        f"再来看看这条新闻：{title}。报道来自{source}，这条消息值得关注。"
        f"简单说一下背景——这个话题最近在行业里的讨论热度比较高，"
        f"很多人都注意到了这个方向的进展。它的重要性在于反映了当前技术发展的一个新趋势。"
        f"对于一直在关注AI领域的朋友来说，这是一个值得留意的信号。"
        f"从实际应用的角度来看，这可能会带来一些相当有意思的产品变化。"
        f"比如在智能助手、代码生成、内容创作这些场景里，我们可能会看到新的可能性。"
        f"{history_ref}"
        f"当然，技术的发展从来不是一蹴而就的。这条消息背后反映了整个行业在某个方向上的共同努力。"
        f"不管是技术层面的突破还是商业模式的创新，都值得我们去理解和消化。"
        f"我们会继续关注这个方向的后续发展。"
    )


def _fallback_zh_low(title: str, source: str, score: int, history_ref: str) -> str:
    """低分中文新闻：250+ 字 ≈ 1分钟口播"""
    return (
        f"快速看一下这条消息：{title}。这是{source}的报道。"
        f"虽然可能不是今天最重要的头条新闻，但对整个行业来说也是一个值得注意的信号。"
        f"简单来说，这说明AI领域的发展正在从多个维度同时向前推进。"
        f"技术研发、产品落地、商业模式创新、监管政策制定，各个方面都在发生着变化。"
        f"每一条新闻背后，都反映着行业的一些细微变化和趋势调整。"
        f"对于从业者和关注AI的朋友来说，花点时间了解这些动态，"
        f"有助于建立更完整的行业认知和判断框架。"
        f"关注细节、关注趋势，才能对行业有更深入的理解。"
        f"{history_ref}"
        f"好了，这条消息就说到这儿。"
    )


def _fallback_en(title: str, source: str, score: int, history_ref: str) -> str:
    """英文新闻脚本：确保足够长度"""
    if score >= 7:
        return (
            f"Let's dive into this major story: {title}. This comes to us from {source}, "
            f"and it's a significant development in the AI space. "
            f"From a technical perspective, this represents a real breakthrough — not just a proof of concept, "
            f"but something that could genuinely change how we build and deploy AI systems. "
            f"For developers and engineers, this means new tools, new APIs, and new ways of working. "
            f"For companies, it could translate into major efficiency gains and entirely new product categories. "
            f"The broader implication is that AI technology is accelerating from research into production, "
            f"and the gap between cutting-edge research and real-world applications is narrowing fast. "
            f"{history_ref}"
            f"We'll be keeping a close eye on how this develops. "
            f"This is exactly the kind of story that makes following AI so exciting right now — "
            f"every week brings something that would have seemed like science fiction just a few years ago. "
            f"And honestly, I think we're still in the early innings of this transformation."
        )
    elif score >= 5:
        return (
            f"Next up: {title}. This story from {source} is worth paying attention to. "
            f"This topic has been generating a fair amount of discussion in the AI community recently, "
            f"and for good reason. It reflects an emerging trend in how AI technology is evolving, "
            f"particularly around practical applications and real-world deployment. "
            f"For those of you building or using AI tools, this is a signal worth noting. "
            f"The implications could range from new product features to shifts in developer workflows. "
            f"{history_ref}"
            f"Of course, technology development is never a straight line — "
            f"there are always twists and turns along the way. But this direction looks promising, "
            f"and we'll be watching to see how it plays out in the coming weeks and months."
        )
    else:
        return (
            f"A quick update from {source}: {title}. "
            f"While this may not be the biggest headline of the day, it's another data point "
            f"showing that AI development is progressing on multiple fronts simultaneously. "
            f"Technology, product design, business models, and regulatory frameworks are all evolving in parallel. "
            f"Each piece of news like this helps build a more complete picture of where the industry is heading. "
            f"{history_ref}"
            f"For those keeping score at home, this is yet another signal that the AI landscape "
            f"continues to shift and evolve at a remarkable pace. Stay tuned for more updates."
        )


def _generate_fallback(news_items: list[dict], related_news: list[dict] | None = None) -> list[dict]:
    """生成连贯的 fallback 脚本（无结尾，24h风格）"""
    scripts: list[dict] = []
    total = len(news_items)
    mentioned_urls = {(n.get("url", "")) for n in (related_news or [])}

    for i, item in enumerate(news_items):
        title = item.get("title", "Unknown")
        source = item.get("source", "Unknown")
        score = item.get("importance_score", 5)
        url = item.get("url", "")

        # 开头过渡：直接连接，无开场白
        prefix = ""
        if i > 0:
            prefix = choice(FALLBACK_TRANSITIONS)

        # 历史相关引用
        history_ref = ""
        if related_news:
            for rn in related_news[:2]:
                rn_title = rn.get("title", "")
                if rn_title and rn_title != title:
                    history_ref = f"这让人想起之前报道过的「{rn_title[:30]}」，可以说是那个方向的延续。"
                    break

        # 根据语言选择模板
        is_en = item.get("language", "zh") == "en"
        if is_en:
            body = _fallback_en(title, source, score, history_ref)
        elif score >= 7:
            body = _fallback_zh_high(title, source, score, history_ref)
        elif score >= 5:
            body = _fallback_zh_mid(title, source, score, history_ref)
        else:
            body = _fallback_zh_low(title, source, score, history_ref)

        scripts.append({
            "news_url": url,
            "title": title,
            "source": source,
            "importance_score": score,
            "script": f"{prefix}{body}",
            "language": item.get("language", "zh"),
            "is_first": i == 0,
            "is_last": False,  # 永远不是最后一条！
        })

    return scripts


async def retrieve_related_news(title: str, limit: int = 5) -> list[dict]:
    """从数据库检索相关历史新闻（简单关键词匹配）"""
    try:
        import aiosqlite
        from app.config import config
        from app.utils.text_utils import extract_keywords

        keywords = extract_keywords(title, top_n=4)
        if not keywords:
            return []

        db = await aiosqlite.connect(config.database_path)
        db.row_factory = aiosqlite.Row

        conditions = " OR ".join(["title LIKE ?" for _ in keywords])
        params = [f"%{kw}%" for kw in keywords]
        cursor = await db.execute(
            f"SELECT title, source, importance_score, url, collected_at FROM news WHERE is_used=1 AND ({conditions}) ORDER BY collected_at DESC LIMIT ?",
            params + [limit],
        )
        rows = await cursor.fetchall()
        await db.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.debug(f"News retrieval failed (non-critical): {e}")
        return []


async def write_scripts_node(state: ScriptWriterState) -> dict:
    """LangGraph 节点：为所有新闻生成连贯的播客脚本（带历史检索）"""
    news_items = state.get("news_items", [])
    if not news_items:
        logger.warning("No news items to write scripts for")
        return {"scripts": [], "status": "completed"}

    # 检索每一条新闻的相关历史
    all_related: list[dict] = []
    for item in news_items[:5]:  # 最多检查前5条
        related = await retrieve_related_news(item.get("title", ""))
        all_related.extend(related)
    # 去重
    seen = set()
    unique_related = []
    for r in all_related:
        if r["title"] not in seen:
            seen.add(r["title"])
            unique_related.append(r)

    news_for_llm = [
        {"index": i, "title": n.get("title", ""), "source": n.get("source", ""),
         "score": n.get("importance_score", 5), "url": n.get("url", "")}
        for i, n in enumerate(news_items)
    ]
    news_json = json.dumps(news_for_llm, ensure_ascii=False, indent=2)
    rag_context = _build_rag_context(unique_related)

    scripts: list[dict] = []
    try:
        llm = llm_factory.create_chat_model(temperature=0.8, streaming=False, timeout=15)
        response = await llm.ainvoke(
            BATCH_SCRIPT_PROMPT.format(news_json=news_json, rag_context=rag_context)
        )
        content = response.content if hasattr(response, "content") else str(response)
        content = content.strip()
        if content.startswith("```"):
            start = content.index("[")
            end = content.rindex("]") + 1
            content = content[start:end]
        llm_scripts = json.loads(content)
    except Exception as e:
        logger.warning(f"LLM script generation failed: {e}, using fallback")
        scripts = _generate_fallback(news_items, unique_related)
        total = sum(len(s["script"]) for s in scripts)
        logger.info(f"[Script Writer] Fallback: {len(scripts)} scripts, {total} chars total")
        return {"scripts": scripts, "status": "completed", "errors": []}

    for i, item in enumerate(news_items):
        llm_entry = llm_scripts[i] if i < len(llm_scripts) else {}
        script_text = llm_entry.get("script", "")
        if len(script_text) < 100:
            script_text = _generate_fallback([item])[0]["script"] if item else ""
        scripts.append({
            "news_url": item.get("url", ""),
            "title": item.get("title", ""),
            "source": item.get("source", ""),
            "importance_score": item.get("importance_score", 5),
            "script": script_text,
            "language": item.get("language", "zh"),
            "is_first": i == 0,
            "is_last": False,
        })

    total_chars = sum(len(s["script"]) for s in scripts)
    logger.info(f"[Script Writer] Generated {len(scripts)} scripts, {total_chars} chars, {len(unique_related)} related")
    return {"scripts": scripts, "status": "completed", "errors": []}
