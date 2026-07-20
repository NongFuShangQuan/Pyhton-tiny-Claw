"""tools._args: 共享参数解析工具。

所有工具执行体接收的 args 可能是 dict / str / bytes。
本模块提供统一的解析函数，消除各文件中的重复代码。
"""
from __future__ import annotations

import json
from typing import Any


def parse_args(args: Any) -> dict[str, Any] | None:
    """将工具输入统一解析为 dict，解析失败返回 None。"""
    if isinstance(args, dict):
        return args
    if isinstance(args, (bytes, bytearray)):
        try:
            return json.loads(bytes(args).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
    if isinstance(args, str):
        try:
            return json.loads(args)
        except json.JSONDecodeError:
            return None
    return None


__all__ = ["parse_args"]
