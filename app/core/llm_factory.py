from __future__ import annotations

from langchain_openai import ChatOpenAI

from app.config import config


async def resolve_active_llm() -> dict:
    """从数据库解析当前激活的 LLM 连接，fallback 到 .env"""
    try:
        import aiosqlite
        db = await aiosqlite.connect(config.database_path)
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM model_connections WHERE service_type='llm' AND is_active=1 LIMIT 1")
        row = await cursor.fetchone()
        await db.close()
        if row:
            return {
                "model": row["model"] or config.dashscope_model,
                "base_url": row["base_url"] or config.dashscope_api_base,
                "api_key": row["api_key"] or config.dashscope_api_key,
            }
    except Exception:
        pass
    return {
        "model": config.dashscope_model,
        "base_url": config.dashscope_api_base,
        "api_key": config.dashscope_api_key,
    }


class LLMFactory:
    @staticmethod
    def create_chat_model(
        model: str | None = None,
        temperature: float = 0.7,
        streaming: bool = True,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: int = 60,
    ) -> ChatOpenAI:
        return ChatOpenAI(
            model=model or config.dashscope_model,
            base_url=base_url or config.dashscope_api_base,
            api_key=api_key or config.dashscope_api_key,
            temperature=temperature,
            streaming=streaming,
            request_timeout=timeout,
        )

    @staticmethod
    def create_structured_model(
        model: str | None = None,
        temperature: float = 0.3,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> ChatOpenAI:
        return ChatOpenAI(
            model=model or config.dashscope_model,
            base_url=base_url or config.dashscope_api_base,
            api_key=api_key or config.dashscope_api_key,
            temperature=temperature,
            streaming=False,
        )

    @staticmethod
    async def create_from_active(temperature: float = 0.7, streaming: bool = True, timeout: int = 60) -> ChatOpenAI:
        """根据数据库中激活的 LLM 连接创建模型"""
        conn = await resolve_active_llm()
        return ChatOpenAI(
            model=conn["model"],
            base_url=conn["base_url"],
            api_key=conn["api_key"],
            temperature=temperature,
            streaming=streaming,
            request_timeout=timeout,
        )


llm_factory = LLMFactory()
