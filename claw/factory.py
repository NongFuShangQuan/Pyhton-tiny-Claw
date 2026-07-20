"""claw.factory: 公共工厂函数——消除各入口点之间的重复代码。"""
from __future__ import annotations

from pathlib import Path

from claw.provider import LLMProvider, NewDeepSeekProvider, NewZhipuOpenAIProvider
from claw.tools import (
    Registry,
    NewBashTool,
    NewEditFileTool,
    NewReadFileTool,
    NewRegistry,
    NewWriteFileTool,
)


def create_provider(name: str, model: str) -> LLMProvider:
    """根据名称创建 LLM Provider（deepseek / zhipu）。"""
    if name == "deepseek":
        return NewDeepSeekProvider(model)
    elif name == "zhipu":
        return NewZhipuOpenAIProvider(model)
    else:
        raise ValueError(f"未知 Provider: '{name}'。可选: deepseek, zhipu")


def build_registry(work_dir: str | Path) -> Registry:
    """创建并注册四个核心工具的 Registry。"""
    wd = str(work_dir)
    registry = NewRegistry()
    registry.register(NewReadFileTool(wd))
    registry.register(NewWriteFileTool(wd))
    registry.register(NewBashTool(wd))
    registry.register(NewEditFileTool(wd))
    return registry


__all__ = ["create_provider", "build_registry"]
