"""engine.reporter: 端侧事件接收器抽象。


由于我们在 Python 项目里不再使用 context.Context 对象作为显式参数，
Reporter 的钩子方法签名省略 ctx 形参。保留 ctx 仅用于未来扩展。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class Reporter(ABC):
    @abstractmethod
    def on_thinking(self, ctx: Optional[Any] = None) -> None:
        ...

    @abstractmethod
    def on_tool_call(
        self,
        tool_name: str,
        args: str,
        ctx: Optional[Any] = None,
    ) -> None:
        ...

    @abstractmethod
    def on_tool_result(
        self,
        tool_name: str,
        result: str,
        is_error: bool,
        ctx: Optional[Any] = None,
    ) -> None:
        ...

    @abstractmethod
    def on_message(self, content: str, ctx: Optional[Any] = None) -> None:
        ...


__all__ = ["Reporter"]