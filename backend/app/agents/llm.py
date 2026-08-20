"""LLM 工厂：根据配置构建聊天模型。

支持 deepseek / openai / anthropic / qwen / ollama / mock。
mock 模式用于无 API Key 时的链路自测，返回规则性响应。
"""
from __future__ import annotations

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from loguru import logger
from pydantic import Field, SecretStr

from app.config import get_settings


class MockChatModel(BaseChatModel):
    """无外部依赖的兜底模型。

    用于测试 / 演示 Agent 状态机与工具调用链路，不产生真实模型开销。
    对包含"工具调用意图"的关键词返回 tool_calls，其余返回规则文本。
    """

    response_text: str = Field(default="mock response")
    model_name: str = "mock-llm"

    def _generate(self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs) -> Any:
        from langchain_core.outputs import ChatGeneration, ChatResult

        last = messages[-1].content if messages else ""
        text = f"{self.response_text} | echo: {str(last)[:120]}"
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])

    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        """Mock 模型不执行真实工具调用，直接返回自身。"""
        return self

    @property
    def _llm_type(self) -> str:
        return "mock-chat-model"


def build_chat_model(settings: Any = None) -> BaseChatModel:
    """根据全局配置构建聊天模型实例。"""
    s = settings or get_settings()

    if s.llm_provider == "deepseek":
        from langchain_deepseek import ChatDeepSeek

        logger.info("使用 DeepSeek 模型: {}", s.deepseek_model)
        return ChatDeepSeek(
            model=s.deepseek_model,
            api_key=SecretStr(s.deepseek_api_key),
            api_base=s.deepseek_base_url or None,
            temperature=s.llm_temperature,
            max_tokens=s.llm_max_tokens,
            timeout=s.llm_timeout,
        )

    if s.llm_provider == "openai":
        from langchain_openai import ChatOpenAI

        logger.info("使用 OpenAI 兼容模型: {}", s.openai_model)
        return ChatOpenAI(
            model=s.openai_model,
            api_key=SecretStr(s.openai_api_key),
            base_url=s.openai_base_url or None,
            temperature=s.llm_temperature,
            max_tokens=s.llm_max_tokens,
            timeout=s.llm_timeout,
        )

    if s.llm_provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        logger.info("使用 Anthropic 模型: {}", s.anthropic_model)
        return ChatAnthropic(
            model=s.anthropic_model,
            api_key=SecretStr(s.anthropic_api_key),
            temperature=s.llm_temperature,
            max_tokens=s.llm_max_tokens,
            timeout=s.llm_timeout,
        )

    if s.llm_provider == "qwen":
        from langchain_openai import ChatOpenAI

        logger.info("使用 Qwen(DashScope) 模型: {}", s.qwen_model)
        return ChatOpenAI(
            model=s.qwen_model,
            api_key=SecretStr(s.dashscope_api_key),
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            temperature=s.llm_temperature,
            max_tokens=s.llm_max_tokens,
            timeout=s.llm_timeout,
        )

    if s.llm_provider == "ollama":
        from langchain_ollama import ChatOllama

        logger.info("使用 Ollama 本地模型: {}", s.ollama_model)
        return ChatOllama(
            model=s.ollama_model,
            base_url=s.ollama_base_url,
            temperature=s.llm_temperature,
            num_predict=s.llm_max_tokens,
        )

    logger.warning("使用 Mock 模型（未配置真实 LLM Provider）")
    return MockChatModel()


def get_llm(settings: Any = None):
    """便捷入口：返回带名称的模型实例。"""
    return build_chat_model(settings)
