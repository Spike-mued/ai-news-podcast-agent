from __future__ import annotations

import json
from random import choice

from loguru import logger

from app.agents.script_writer.state import ScriptWriterState
from app.core.llm_factory import llm_factory
from app.utils.prompt_loader import load_prompt

# 角色定义 — 参考 Podcast-Generator 的 podUsers 配置
HOST = "主持人"
EXPERT = "技术专家"

SINGLE_STAGE_PROMPT = """你是一个24小时不间断AI新闻播客的脚本撰写人。请为一组AI/科技新闻撰写双人对话播客脚本。

## 角色定义
- **{host}**：掌控节奏、引出话题、提问引导、过渡衔接。风格轻松亲和，口语化表达。
- **{expert}**：深度解读技术细节、分析行业影响、补充专业观点。风格专业但不晦涩。

## 对话规则
- 每条新闻的对话 3-5 轮交替（{host}↔{expert}），有问有答，像两个朋友聊天
- **严禁任何结束语**！不要说"下期再见""以上就是今天""感谢收听""我们下回再聊""这期节目就到这里""欢迎收听""大家好"等
- 直接进入话题，像一直在播的电台一样自然接续，第一条新闻也不需要开场白
- 新闻之间的过渡由{host}自然引出下一条

## 新闻之间过渡示例
- "说到AI，还有一个消息值得关注..."
- "紧接着来看看下一条新闻。"
- "同样值得关注的还有这个。"
- "换个角度，再来看一条相关消息。"

## 对话长度
- 重要性9-10分：5-6轮对话，总计600-800字
- 重要性7-8分：4-5轮对话，总计400-600字
- 重要性4-6分：3-4轮对话，总计250-400字

## 风格
- **必须全部使用中文！** 所有新闻内容（包括原本是英文的新闻）必须翻译为中文进行播报
- 技术术语可保留英文原文，但新闻标题和内容必须翻译为中文
- 口语化，朋友聊天风格
- 适当加入"说实话""有意思的是""大家猜怎么着""这个点特别值得展开聊聊"等口语表达
- {expert}可以委婉补充或深化{host}的观点
- {host}可以表达惊讶、好奇来引出{expert}的专业解读

{rag_context}

## 新闻列表（按重要性排序）
{news_json}

请严格返回JSON数组：
[{{"news_url": "...", "dialogue": [{{"speaker": "{host}", "text": "..."}}, {{"speaker": "{expert}", "text": "..."}}]}}, ...]
只返回JSON数组，不要其他任何文字。"""


# ---- Fallback 模板 (双人对话版) ----

_FALLBACK_TRANSITIONS_HOST = [
    "说到AI领域，再来看另一个消息。",
    "紧接着来看看下一条新闻。",
    "同样值得关注的还有这个消息。",
    "换个角度，再来看一条相关新闻。",
    "接下来这条也很有意思。",
    "另外一边，还有一条消息值得关注。",
    "再说说另一个方向的发展。",
]

_EXPERT_OPENINGS = [
    "没错，这条新闻确实值得好好聊聊。",
    "对，这个消息分量很重。",
    "是的，我也注意到了这个动向。",
    "嗯，这确实是个重要的信号。",
    "说得对，这个方向最近很受关注。",
]


def _fallback_dialogue_high(title: str, source: str, score: int, history_ref: str) -> list[dict]:
    """高重要性：5轮对话 ~600字"""
    return [
        {"speaker": HOST, "text": f"先来看看这条重磅消息：{title}。这条新闻来自{source}，分量非常重，我们来仔细聊一聊。"},
        {"speaker": EXPERT, "text": "没错，这条新闻确实值得深入解读。从技术角度来看，这代表了一个重要的行业突破。它不只是一个概念验证，而是真正有可能改变现有技术格局的东西。对于开发者来说，这意味着新的工具链、新的API、新的工作方式。"},
        {"speaker": HOST, "text": "那对企业端和普通用户来说，会有什么直接影响吗？"},
        {"speaker": EXPERT, "text": f"对企业来说，这可能带来效率上的质的飞跃，甚至改变整个业务流程。对于普通用户，虽然可能感觉不到底层技术的变化，但产品的智能化程度会大大提高。{history_ref}说实话，从整个行业生态来看，这类消息的密集出现说明AI技术正在加速落地，不再是纸上谈兵。"},
        {"speaker": HOST, "text": "技术成熟度、商业可行性、用户接受度，这三个维度确实都在同步推进。我们会持续跟踪这个方向的后续进展，有新消息第一时间在这里更新。"},
    ]


def _fallback_dialogue_mid(title: str, source: str, score: int, history_ref: str) -> list[dict]:
    """中重要性：4轮对话 ~450字"""
    return [
        {"speaker": HOST, "text": f"再来看看这条新闻：{title}。报道来自{source}，这条消息值得关注。"},
        {"speaker": EXPERT, "text": "对，这个消息反映了一个很有意思的趋势。简单说一下背景——这个话题最近在行业里的讨论热度比较高。它的重要性在于反映了当前技术发展的一个新方向，对于一直在关注AI领域的朋友来说，这是一个值得留意的信号。"},
        {"speaker": HOST, "text": "从实际应用的角度来看，这会带来什么具体变化吗？"},
        {"speaker": EXPERT, "text": f"在智能助手、代码生成、内容创作这些场景里，我们可能会看到新的可能性。{history_ref}当然，技术的发展从来不是一蹴而就的，这条消息背后反映了整个行业在某个方向上的共同努力，值得持续关注。"},
    ]


def _fallback_dialogue_low(title: str, source: str, score: int, history_ref: str) -> list[dict]:
    """低重要性：3轮对话 ~300字"""
    return [
        {"speaker": HOST, "text": f"快速看一下这条消息：{title}。这是{source}的报道。虽然可能不是今天最重要的头条，但对整个行业来说也是一个值得注意的信号。"},
        {"speaker": EXPERT, "text": f"是的。简单来说，这说明AI领域的发展正在从多个维度同时向前推进——技术研发、产品落地、商业模式创新，各个方面都在发生着变化。{history_ref}"},
        {"speaker": HOST, "text": "关注细节、关注趋势，才能对行业有更深入的理解。好了，这条消息就到这儿。"},
    ]


def _fallback_en_dialogue(title: str, source: str, score: int, history_ref: str) -> list[dict]:
    """英文来源新闻 → 中文播报（自动翻译）"""
    if score >= 7:
        return [
            {"speaker": HOST, "text": f"来看看来自{source}的重磅消息：{title}。这条新闻在AI领域引起了广泛关注，我们仔细聊聊。"},
            {"speaker": EXPERT, "text": "没错，从技术角度来看，这确实是一个重要突破。不仅仅是概念验证，而是真正可能改变AI系统构建方式的东西。对于开发者来说，这意味着新的工具链、新的API和新的工作方式。"},
            {"speaker": HOST, "text": "那对企业端和普通用户来说呢？"},
            {"speaker": EXPERT, "text": f"对企业来说，可能带来显著的效率提升和全新的产品形态。{history_ref}从更宏观的视角看，这类消息说明AI技术正从研究加速走向生产落地。我们会持续关注后续发展。"},
            {"speaker": HOST, "text": "这种消息正是让人对AI领域保持兴奋的原因——每周都有几年前还像科幻小说的东西变成现实。"},
        ]
    elif score >= 5:
        return [
            {"speaker": HOST, "text": f"接下来看看来自{source}的新闻：{title}。这条消息值得关注。"},
            {"speaker": EXPERT, "text": "是的，这个话题最近在AI社区讨论度比较高，反映了AI技术演进的一个新趋势，特别是在实际应用和部署方面。"},
            {"speaker": HOST, "text": "开发者和从业者应该关注什么？"},
            {"speaker": EXPERT, "text": f"对于使用AI工具的人来说，这是一个值得注意的信号。{history_ref}技术发展从来不是一帆风顺的，但这个方向看起来很有前景，我们继续观察。"},
        ]
    else:
        return [
            {"speaker": HOST, "text": f"快速看一下来自{source}的消息：{title}。虽然不是今天的头条，但也是AI领域发展的一个注脚。"},
            {"speaker": EXPERT, "text": f"确实。每一条这样的新闻都在帮我们构建更完整的行业认知。{history_ref}"},
            {"speaker": HOST, "text": "AI领域的变化速度确实令人瞩目，我们继续关注。"},
        ]


def _generate_fallback(news_items: list[dict], related_news: list[dict] | None = None) -> list[dict]:
    """生成双人对话 fallback 脚本"""
    scripts: list[dict] = []
    used_transitions: list[str] = []

    for i, item in enumerate(news_items):
        title = item.get("title", "Unknown")
        source = item.get("source", "Unknown")
        score = item.get("importance_score", 5)
        url = item.get("url", "")

        history_ref = ""
        if related_news:
            for rn in related_news[:2]:
                rn_title = rn.get("title", "")
                if rn_title and rn_title != title:
                    history_ref = f"这让人想起之前报道过的「{rn_title[:30]}」，可以说是那个方向的延续。"
                    break

        is_en = item.get("language", "zh") == "en"
        if is_en:
            dialogue = _fallback_en_dialogue(title, source, score, history_ref)
        elif score >= 7:
            dialogue = _fallback_dialogue_high(title, source, score, history_ref)
        elif score >= 5:
            dialogue = _fallback_dialogue_mid(title, source, score, history_ref)
        else:
            dialogue = _fallback_dialogue_low(title, source, score, history_ref)

        # 为第一条之后的新闻添加过渡语
        if i > 0:
            trans = choice([t for t in _FALLBACK_TRANSITIONS_HOST if t not in used_transitions] or _FALLBACK_TRANSITIONS_HOST)
            used_transitions.append(trans)
            dialogue[0]["text"] = trans + " " + dialogue[0]["text"]

        # 随机变一下专家开场白
        if len(dialogue) >= 2 and dialogue[1]["speaker"] == EXPERT:
            if choice([True, False]):
                dialogue[1]["text"] = choice(_EXPERT_OPENINGS) + " " + dialogue[1]["text"]

        combined = "\n".join(f"{d['speaker']}：{d['text']}" for d in dialogue)

        scripts.append({
            "news_url": url,
            "title": title,
            "source": source,
            "importance_score": score,
            "script": combined,
            "dialogue": dialogue,
            "language": item.get("language", "zh"),
            "is_first": i == 0,
            "is_last": False,
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


def _build_rag_context(related_news: list[dict]) -> str:
    if not related_news:
        return ""
    lines = ["## 近期已播报的相关新闻（避免重复，可引用）"]
    for n in related_news[:5]:
        lines.append(f"- [{n.get('source','')}] {n.get('title','')} (评分{n.get('importance_score',0)})")
    return "\n".join(lines) + "\n"


def _parse_llm_response(content: str) -> list[dict] | None:
    """解析 LLM 返回的 JSON"""
    content = content.strip()
    if content.startswith("```"):
        try:
            start = content.index("[")
            end = content.rindex("]") + 1
            content = content[start:end]
        except ValueError:
            pass
    return json.loads(content)


def _dialogue_to_scripts(news_items: list[dict], llm_dialogues: list[dict]) -> list[dict]:
    """将 LLM 返回的 dialogue 数组转换为 scripts 格式"""
    scripts: list[dict] = []
    for i, item in enumerate(news_items):
        llm_entry = llm_dialogues[i] if i < len(llm_dialogues) else {}
        dialogue = llm_entry.get("dialogue", [])

        if not dialogue or len(dialogue) < 2:
            # LLM 返回的对话不完整，对这个 item 用 fallback
            fb = _generate_fallback([item])
            if fb:
                scripts.append(fb[0])
            continue

        combined = "\n".join(f"{d.get('speaker', '')}：{d.get('text', '')}" for d in dialogue)

        scripts.append({
            "news_url": item.get("url", ""),
            "title": item.get("title", ""),
            "source": item.get("source", ""),
            "importance_score": item.get("importance_score", 5),
            "script": combined,
            "dialogue": dialogue,
            "language": item.get("language", "zh"),
            "is_first": i == 0,
            "is_last": False,
        })

    return scripts


async def _generate_single_stage(news_items: list[dict], related_news: list[dict]) -> list[dict]:
    """单阶段生成：直接生成双人对话脚本（≤5条新闻时使用）"""
    news_for_llm = [
        {"index": i, "title": n.get("title", ""), "source": n.get("source", ""),
         "score": n.get("importance_score", 5), "url": n.get("url", "")}
        for i, n in enumerate(news_items)
    ]
    news_json = json.dumps(news_for_llm, ensure_ascii=False, indent=2)
    rag_context = _build_rag_context(related_news)

    try:
        llm = await llm_factory.create_from_active(temperature=0.8, streaming=False, timeout=60)
        prompt = SINGLE_STAGE_PROMPT.format(
            host=HOST, expert=EXPERT,
            news_json=news_json,
            rag_context=rag_context,
        )
        response = await llm.ainvoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        llm_dialogues = _parse_llm_response(content)
        return _dialogue_to_scripts(news_items, llm_dialogues)
    except Exception as e:
        logger.warning(f"Single-stage LLM failed: {e}, using fallback")
        return _generate_fallback(news_items, related_news)


async def _generate_two_stage(news_items: list[dict], related_news: list[dict]) -> list[dict]:
    """两阶段生成：大纲 → 双人对话脚本（>5条新闻时使用，参考 Podcast-Generator）"""
    news_for_llm = [
        {"index": i, "title": n.get("title", ""), "source": n.get("source", ""),
         "score": n.get("importance_score", 5), "url": n.get("url", "")}
        for i, n in enumerate(news_items)
    ]
    news_json = json.dumps(news_for_llm, ensure_ascii=False, indent=2)
    rag_context = _build_rag_context(related_news)

    # 阶段 1：生成大纲
    try:
        llm = await llm_factory.create_from_active(temperature=0.3, streaming=False, timeout=60)
        outline_prompt = load_prompt("script_outline.j2", news_json=news_json)
        response = await llm.ainvoke(outline_prompt)
        content = response.content if hasattr(response, "content") else str(response)
        outline = _parse_llm_response(content)
        outline_json = json.dumps(outline, ensure_ascii=False, indent=2)
        logger.info(f"[Outline] Generated {len(outline.get('segments', []))} segments")
    except Exception as e:
        logger.warning(f"Outline generation failed: {e}, falling back to single-stage")
        return await _generate_single_stage(news_items, related_news)

    # 阶段 2：根据大纲生成对话脚本
    try:
        llm2 = await llm_factory.create_from_active(temperature=0.8, streaming=False, timeout=60)
        dialogue_prompt = load_prompt(
            "script_dialogue.j2",
            outline_json=outline_json,
            news_json=news_json,
            rag_context=rag_context,
        )
        response = await llm2.ainvoke(dialogue_prompt)
        content = response.content if hasattr(response, "content") else str(response)
        llm_dialogues = _parse_llm_response(content)
        return _dialogue_to_scripts(news_items, llm_dialogues)
    except Exception as e:
        logger.warning(f"Dialogue generation failed: {e}, using fallback")
        return _generate_fallback(news_items, related_news)


# ---- LangGraph 节点入口 ----

async def write_scripts_node(state: ScriptWriterState) -> dict:
    """LangGraph 节点：为新闻生成双人对话播客脚本（支持智能两阶段）"""
    news_items = state.get("news_items", [])
    if not news_items:
        logger.warning("No news items to write scripts for")
        return {"scripts": [], "status": "completed"}

    # RAG：检索历史相关新闻
    all_related: list[dict] = []
    for item in news_items[:5]:
        related = await retrieve_related_news(item.get("title", ""))
        all_related.extend(related)
    seen = set()
    unique_related = []
    for r in all_related:
        if r["title"] not in seen:
            seen.add(r["title"])
            unique_related.append(r)

    # 智能路由：>5条用两阶段，≤5条用单阶段
    use_two_stage = len(news_items) > 5
    stage_label = "two-stage (outline→dialogue)" if use_two_stage else "single-stage"
    logger.info(f"[Script Writer] {len(news_items)} news items → {stage_label}")

    if use_two_stage:
        scripts = await _generate_two_stage(news_items, unique_related)
    else:
        scripts = await _generate_single_stage(news_items, unique_related)

    total_chars = sum(len(s["script"]) for s in scripts)
    total_turns = sum(len(s.get("dialogue", [])) for s in scripts)
    logger.info(f"[Script Writer] {len(scripts)} scripts, {total_turns} dialogue turns, {total_chars} chars")
    return {"scripts": scripts, "status": "completed", "errors": []}
