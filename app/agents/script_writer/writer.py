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

        # 无结束语的主内容（长度≥250字确保1分钟+）
        if score >= 7:
            body = (
                f"先来看看{title}。这条来自{source}的消息非常有分量。"
                f"我们仔细聊聊这个事——首先从技术角度看，这确实代表了一个重要突破。"
                f"它不仅仅是概念验证，而是真正可能改变行业格局的东西。"
                f"对开发者来说，这意味着新的工具链和工作方式；"
                f"对企业来说，这可能带来效率的质的飞跃；"
                f"对普通用户来说，体验上的提升会非常明显。"
                f"{history_ref}"
                f"从整个行业生态来看，这类消息的密集出现说明技术正在加速落地。"
                f"我们也会持续跟踪这个方向的后续进展，有新消息第一时间更新。"
            )
        elif score >= 5:
            body = (
                f"来看看{title}。这个消息来自{source}。"
                f"简单说一下背景——这个话题最近在行业里讨论得比较多。"
                f"它的重要性在于反映了当前技术发展的一个新方向。"
                f"对于一直在关注AI领域的朋友来说，这是值得留意的信号。"
                f"从实际应用的角度看，可能会带来一些有意思的产品变化。"
                f"{history_ref}"
            )
        else:
            body = (
                f"快速看看{title}。{source}的报道。"
                f"虽然可能不是今天最重要的消息，但对行业也是一个信号。"
                f"简单来说，这说明AI领域的发展正在从多个维度同时推进。"
                f"每条新闻背后都反映着行业的一些细微变化。"
            )

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
