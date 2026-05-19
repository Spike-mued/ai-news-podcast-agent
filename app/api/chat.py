"""Chat API — SSE 流式 Chroma RAG 新闻知识问答"""
from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel

from app.core.llm_factory import llm_factory
from app.rag.chroma_store import search_news

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str


QA_PROMPT = """你是AI新闻知识助手。基于提供的新闻资料回答用户问题。

规则：
- 只基于资料回答，不编造信息
- 资料中没有相关信息时，说"暂无相关新闻"
- 简洁专业，3-8句话
- 全部使用中文

资料:
{context}

问题: {question}
回答:"""


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/send")
async def chat_send(req: ChatRequest):
    """SSE 流式 Chat"""
    message = req.message.strip()
    if not message:
        return StreamingResponse(
            iter([_sse({"type":"error","content":"请输入内容"}), _sse({"type":"done"})]),
            media_type="text/event-stream")

    # 在生成器外部做 RAG 检索
    results = search_news(message, source="global", top_k=5)
    if not results:
        return StreamingResponse(
            iter([_sse({"type":"status","content":"检索中..."}),
                  _sse({"type":"token","content":"抱歉，知识库中没有找到相关信息。试试换个问法？"}),
                  _sse({"type":"done"})]),
            media_type="text/event-stream")

    context = "\n\n".join(
        f"[{r['source']}] {r['title']}\n{r.get('content','')[:300]}" for r in results
    )
    sources = [{"title": r["title"], "source": r["source"]} for r in results[:3]]
    prompt = QA_PROMPT.format(context=context, question=message)

    # 在生成器外部创建 LLM（避免 async generator 中的 await 问题）
    llm = llm_factory.create_chat_model(temperature=0.5, streaming=True, timeout=30)

    async def generate():
        yield _sse({"type":"status","content":"检索中..."})
        yield _sse({"type":"sources","sources":sources})

        try:
            async for chunk in llm.astream(prompt):
                token = chunk.content if hasattr(chunk, "content") else str(chunk)
                if token:
                    yield _sse({"type":"token","content":token})
        except Exception as e:
            logger.error(f"LLM stream failed: {e}")
            yield _sse({"type":"token","content":"抱歉，生成回答时出错。"})

        yield _sse({"type":"done"})

    return StreamingResponse(generate(), media_type="text/event-stream",
        headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})
