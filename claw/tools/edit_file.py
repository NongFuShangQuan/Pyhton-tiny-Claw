"""tools.edit_file: 局部字符串替换编辑。

对应 Go 版 internal/tools/edit_file.go。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..schema import ToolDefinition
from ._args import parse_args
from .registry import BaseTool


class EditFileTool(BaseTool):
    def __init__(self, work_dir: str | os.PathLike):
        self.work_dir = Path(work_dir)

    def name(self) -> str:
        return "edit_file"

    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name(),
            description="对现有文件进行局部的字符串替换。这比重写整个文件更安全、更快速。请提供足够的 old_text 上下文以确保匹配的唯一性。",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要修改的文件路径",
                    },
                    "old_text": {
                        "type": "string",
                        "description": "文件中原有的文本。必须包含足够的上下文，以确保在文件中的唯一性。",
                    },
                    "new_text": {
                        "type": "string",
                        "description": "要替换成的新文本",
                    },
                },
                "required": ["path", "old_text", "new_text"],
            },
        )

    def execute(self, args: Any) -> str:
        input_data = parse_args(args)
        if input_data is None:
            return "Error: 参数解析失败: 非法 JSON"
        rel = input_data.get("path", "")
        old_text = input_data.get("old_text", "")
        new_text = input_data.get("new_text", "")
        if not rel:
            return "Error: 缺少 path 参数"

        full = (self.work_dir / rel).resolve()
        try:
            full.relative_to(self.work_dir.resolve(strict=False))
        except ValueError:
            return "Error: 路径越界，禁止修改工作区外的文件。"

        try:
            original = full.read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError as e:
            return f"Error: 读取文件失败，请确认路径是否正确: {e}"
        except OSError as e:
            return f"Error: 读取文件失败: {e}"

        try:
            new_content = fuzzy_replace(original, old_text, new_text)
        except ValueError as e:
            return f"Error: {e}"

        try:
            full.write_text(new_content, encoding="utf-8")
        except OSError as e:
            return f"Error: 写回文件失败: {e}"

        return f"✅ 成功修改文件: {rel}"


def NewEditFileTool(work_dir: str | os.PathLike) -> "EditFileTool":
    return EditFileTool(work_dir)


def fuzzy_replace(original_content: str, old_text: str, new_text: str) -> str:
    """四级模糊替换: 精确 -> 换行归一化 -> Trim Space -> 逐行去缩进。"""
    # L1: 精确匹配
    count = original_content.count(old_text)
    if count == 1:
        return original_content.replace(old_text, new_text, 1)
    if count > 1:
        raise ValueError(
            f"old_text 匹配到了 {count} 处，请提供更多的上下文代码以确保唯一性"
        )

    # L2: 换行符归一化
    norm_content = original_content.replace("\r\n", "\n")
    norm_old = old_text.replace("\r\n", "\n")

    count = norm_content.count(norm_old)
    if count == 1:
        return norm_content.replace(norm_old, new_text, 1)

    # L3: Trim Space 匹配
    trimmed_old = norm_old.strip()
    if trimmed_old:
        count = norm_content.count(trimmed_old)
        if count == 1:
            return norm_content.replace(trimmed_old, new_text, 1)

    # L4: 逐行去缩进匹配
    return line_by_line_replace(norm_content, norm_old, new_text)


def line_by_line_replace(content: str, old_text: str, new_text: str) -> str:
    content_lines = content.split("\n")
    old_lines = old_text.strip().split("\n")

    if not old_lines or len(content_lines) < len(old_lines):
        raise ValueError("找不到该代码片段")

    old_lines = [line.strip() for line in old_lines]

    match_count = 0
    match_start = -1
    match_end = -1

    for i in range(len(content_lines) - len(old_lines) + 1):
        is_match = True
        for j, ol in enumerate(old_lines):
            if content_lines[i + j].strip() != ol:
                is_match = False
                break
        if is_match:
            match_count += 1
            match_start = i
            match_end = i + len(old_lines)

    if match_count == 0:
        raise ValueError("在文件中未找到 old_text，请检查内容和缩进")
    if match_count > 1:
        raise ValueError(f"模糊匹配到了 {match_count} 处代码，请提供更多上下文以定位")

    new_lines = content_lines[:match_start] + [new_text] + content_lines[match_end:]
    return "\n".join(new_lines)


__all__ = [
    "EditFileTool",
    "NewEditFileTool",
    "fuzzy_replace",
    "line_by_line_replace",
]