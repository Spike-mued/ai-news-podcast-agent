from __future__ import annotations

from langchain_openai import ChatOpenAI

from app.config import config


class LLMFactory:
    @staticmethod
    def create_chat_model(
        model: str | None = None,
        temperature: float = 0.7,
        streaming: bool = True,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> ChatOpenAI:
        return ChatOpenAI(
            model=model or config.dashscope_model,
            base_url=base_url or config.dashscope_api_base,
            api_key=api_key or config.dashscope_api_key,
            temperature=temperature,
            streaming=streaming,
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


llm_factory = LLMFactory()
