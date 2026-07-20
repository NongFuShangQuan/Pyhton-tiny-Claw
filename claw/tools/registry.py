"""tools.registry: 工具注册中心与中间件链。

对应 Go 版 internal/tools/registry.go。
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Optional

from ..schema import ToolCall, ToolDefinition, ToolResult
from ..observability.trace import TraceContext, Span, StartSpan, EndSpan, AddAttribute


_logger = logging.getLogger("claw.registry")


class BaseTool(ABC):
    """所有工具必须满足的统一接口。"""

    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def definition(self) -> ToolDefinition:
        ...

    @abstractmethod
    def execute(self, args: Any) -> str:
        """args 可以是 dict / str / bytes。"""
        ...


# 中间件签名: (call) -> (allowed, reject_reason)
MiddlewareFunc = Callable[[ToolCall], "tuple[bool, str]"]


class Registry(ABC):
    """Registry 抽象。"""

    @abstractmethod
    def register(self, tool: BaseTool) -> None:
        ...

    @abstractmethod
    def use(self, mw: MiddlewareFunc) -> None:
        ...

    @abstractmethod
    def get_available_tools(self) -> list[ToolDefinition]:
        ...

    @abstractmethod
    def execute(self, ctx: Optional[TraceContext], call: ToolCall) -> ToolResult:
        ...


class RegistryImpl(Registry):
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}
        self._middlewares: list[MiddlewareFunc] = []

    def use(self, mw: MiddlewareFunc) -> None:
        self._middlewares.append(mw)

    def register(self, tool: BaseTool) -> None:
        n = tool.name()
        if n in self._tools:
            _logger.warning("[Warning] 工具 '%s' 已经被注册，将被覆盖。", n)
        self._tools[n] = tool
        _logger.info("[Registry] 成功挂载工具: %s", n)

    def get_available_tools(self) -> list[ToolDefinition]:
        return [t.definition() for t in self._tools.values()]

    def execute(self, ctx: Optional[TraceContext], call: ToolCall) -> ToolResult:
        """带埋点 + 中间件拦截的工具执行。"""
        ctx, span = StartSpan(ctx, "Tool.Execute")
        AddAttribute(span, "tool_name", call.name)
        AddAttribute(span, "arguments", call.arguments_to_str())

        try:
            tool = self._tools.get(call.name)
            if tool is None:
                return ToolResult(
                    tool_call_id=call.id,
                    output=f"Error: 系统中不存在名为 '{call.name}' 的工具。",
                    is_error=True,
                )

            # 中间件链
            for mw in self._middlewares:
                try:
                    allowed, reason = mw(call)
                except Exception as e:
                    allowed, reason = False, f"中间件异常: {e}"
                if not allowed:
                    _logger.warning(
                        "[Registry] ⚠️ 工具 %s 被 Middleware 拦截: %s", call.name, reason
                    )
                    AddAttribute(span, "intercepted", True)
                    AddAttribute(span, "reject_reason", reason)
                    return ToolResult(
                        tool_call_id=call.id,
                        output=f"执行被系统拦截。原因: {reason}",
                        is_error=True,
                    )

            try:
                output = tool.execute(call.arguments)
            except Exception as e:
                return ToolResult(
                    tool_call_id=call.id,
                    output=f"Error executing {call.name}: {e}",
                    is_error=True,
                )

            AddAttribute(span, "output_preview", _truncate(output, 100))

            return ToolResult(
                tool_call_id=call.id,
                output=output,
                is_error=False,
            )
        finally:
            EndSpan(span)


def NewRegistry() -> Registry:
    return RegistryImpl()


def _truncate(s: str, max_len: int) -> str:
    if len(s) > max_len:
        return s[:max_len] + "..."
    return s


__all__ = [
    "BaseTool",
    "MiddlewareFunc",
    "Registry",
    "RegistryImpl",
    "NewRegistry",
]