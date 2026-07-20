"""provider.interface: LLM 适配层统一接口。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Optional

from ..schema import Message, ToolDefinition


class LLMProvider(ABC):
    """LLMProvider 定义了所有大模型适配器必须满足的统一接口。"""

    @abstractmethod
    def generate(
        self,
        messages: list[Message],
        available_tools: Optional[list[ToolDefinition]] = None,
    ) -> Message:
        """接收当前上下文历史与可用工具列表，返回模型响应消息。"""
        raise NotImplementedError


# 兼容别名：Go 版使用 Generate 方法名
def generate(provider: LLMProvider, messages: list[Message], tools=None) -> Message:
    return provider.generate(messages, tools)


__all__ = ["LLMProvider"]