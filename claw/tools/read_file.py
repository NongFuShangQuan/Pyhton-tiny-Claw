"""tools.read_file: 读取工作区内文件。

对应 Go 版 internal/tools/read_file.go。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..schema import ToolDefinition
from ._args import parse_args
from .registry import BaseTool


class ReadFileTool(BaseTool):
    def __init__(self, work_dir: str | os.PathLike):
        self.work_dir = Path(work_dir)

    def name(self) -> str:
        return "read_file"

    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name(),
            description="读取指定路径的文件内容。请提供相对工作区的路径。",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要读取的文件路径，如 cmd/claw/main.py",
                    },
                },
                "required": ["path"],
            },
        )

    def execute(self, args: Any) -> str:
        input_data = parse_args(args)
        if input_data is None:
            return "Error: 参数解析失败: 非法 JSON"
        rel = input_data.get("path", "")
        if not rel:
            return "Error: 缺少 path 参数"

        full = (self.work_dir / rel).resolve()
        # 防止越权读取
        try:
            full.relative_to(self.work_dir.resolve(strict=False))
        except ValueError:
            return "Error: 路径越界，禁止读取工作区外的文件。"

        try:
            content = full.read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError as e:
            return f"Error: 打开文件失败: {e}"
        except OSError as e:
            return f"Error: 读取文件内容失败: {e}"

        max_len = 8000
        if len(content) > max_len:
            return (
                f"{content[:max_len]}\n\n...[由于内容过长，已被系统截断至前 {max_len} 字节]..."
            )
        return content


def NewReadFileTool(work_dir: str | os.PathLike) -> "ReadFileTool":
    return ReadFileTool(work_dir)


__all__ = ["ReadFileTool", "NewReadFileTool"]