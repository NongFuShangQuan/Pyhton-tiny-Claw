"""observability.trace: 轻量级链路追踪 (Span 树 + JSON 导出)。


由于 Python 没有 context.WithValue 这种弱类型上下文，我们用一个简单的 Context
类把当前 Span 显式传递下去，避免线程安全问题。
"""
from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class Span:
    name: str
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    duration_ms: int = 0
    attributes: dict[str, Any] = field(default_factory=dict)
    children: list["Span"] = field(default_factory=list)

    _mu: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def end_span(self) -> None:
        """结束当前 Span 并计算耗时。"""
        self.end_time = time.time()
        self.duration_ms = int((self.end_time - self.start_time) * 1000)

    def add_attribute(self, key: str, value: Any) -> None:
        """记录关键元数据。"""
        with self._mu:
            self.attributes[key] = value

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "attributes": dict(self.attributes),
            "children": [c.to_dict() for c in self.children],
        }


class TraceContext:
    """显式携带当前调用链上的父 Span，避免使用弱类型 Context。"""

    __slots__ = ("span",)

    def __init__(self, span: Optional[Span] = None):
        self.span = span

    def with_span(self, span: Span) -> "TraceContext":
        return TraceContext(span)


def StartSpan(
    ctx: Optional[TraceContext] = None, name: str = ""
) -> tuple[TraceContext, Span]:
    """开启一个新的追踪跨度，并将其级联到 ctx 中。"""
    span = Span(name=name)
    if ctx is not None and ctx.span is not None:
        with ctx.span._mu:
            ctx.span.children.append(span)
    return TraceContext(span), span


def EndSpan(span: Span) -> None:
    span.end_span()


def AddAttribute(span: Span, key: str, value: Any) -> None:
    span.add_attribute(key, value)


def ExportTraceToFile(
    root_span: Span, work_dir: str | os.PathLike, session_id: str
) -> None:
    """将根 Span 序列化为 JSON 文件。"""
    trace_dir = Path(work_dir) / ".claw" / "traces"
    trace_dir.mkdir(parents=True, exist_ok=True)

    filename = trace_dir / f"trace_{session_id}_{int(time.time() * 1e9)}.json"

    try:
        data = json.dumps(root_span.to_dict(), indent=2, ensure_ascii=False)
        filename.write_text(data, encoding="utf-8")
    except OSError:
        pass


__all__ = [
    "Span",
    "TraceContext",
    "StartSpan",
    "EndSpan",
    "AddAttribute",
    "ExportTraceToFile",
]