"""tools.write_file: 创建或覆盖写入文件。

对应 Go 版 internal/tools/write_file.go。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..schema import ToolDefinition
from ._args import parse_args
from .registry import BaseTool


class WriteFileTool(BaseTool):
    def __init__(self, work_dir: str | os.PathLike):
        self.work_dir = Path(work_dir)

    def name(self) -> str:
        return "write_file"

    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name(),
            description="创建或覆盖写入一个文件。如果目录不存在会自动创建。请提供相对于工作区的相对路径。",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要写入的文件路径，如 src/main.py",
                    },
                    "content": {
                        "type": "string",
                        "description": "要写入的完整文件内容",
                    },
                },
                "required": ["path", "content"],
            },
        )

    def execute(self, args: Any) -> str:
        input_data = parse_args(args)
        if input_data is None:
            return "Error: 参数解析失败: 非法 JSON"
        rel = input_data.get("path", "")
        content = input_data.get("content", "")
        if not rel:
            return "Error: 缺少 path 参数"

        full = (self.work_dir / rel).resolve()
        # 防止越权写到工作区之外
        try:
            full.relative_to(self.work_dir.resolve(strict=False))
        except ValueError:
            return "Error: 路径越界，禁止写入工作区外的文件。"

        try:
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(content, encoding="utf-8")
        except OSError as e:
            return f"Error: 写入文件失败: {e}"

        return f"成功将内容写入到文件: {rel}"


def NewWriteFileTool(work_dir: str | os.PathLike) -> "WriteFileTool":
    return WriteFileTool(work_dir)


__all__ = ["WriteFileTool", "NewWriteFileTool"]