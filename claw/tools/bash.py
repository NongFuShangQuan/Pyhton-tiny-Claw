"""tools.bash: 工作区内执行任意 bash 命令。

对应 Go 版 internal/tools/bash.go。
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from ..schema import ToolDefinition
from ._args import parse_args
from .registry import BaseTool


_IS_WINDOWS = os.name == "nt"


class BashTool(BaseTool):
    def __init__(self, work_dir: str | os.PathLike):
        self.work_dir = str(work_dir)

    def name(self) -> str:
        return "bash"

    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name(),
            description="在当前工作区执行任意的 bash 命令。支持链式命令(如 &&)。返回标准输出(stdout)和标准错误(stderr)。",
            input_schema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "要执行的 bash 命令",
                    },
                },
                "required": ["command"],
            },
        )

    def execute(self, args: Any) -> str:
        input_data = parse_args(args)
        if input_data is None:
            return "Error: 参数解析失败: 非法 JSON"

        command = input_data.get("command", "")
        if not command:
            return "Error: 缺少 command 参数"

        try:
            shell_exec = _choose_shell()
            proc = subprocess.run(
                shell_exec + (command,),
                cwd=self.work_dir,
                capture_output=True,
                text=True,
                timeout=30,
                # Windows 平台下显式禁用编码错误
                encoding="utf-8",
                errors="replace",
            )
        except subprocess.TimeoutExpired:
            output = ""
            return f"{output}\n[警告: 命令执行超时(30s)，已被系统强制终止。]"
        except FileNotFoundError:
            return (
                "执行报错: 系统未找到 shell 程序。\n"
                "提示：在不支持 bash 的环境中执行 BashTool 可能需要安装 Git Bash 或 WSL。"
            )

        output = proc.stdout or ""
        stderr = proc.stderr or ""
        if stderr:
            output = (output + "\n" + stderr).strip()

        if proc.returncode != 0:
            return f"执行报错: exit code {proc.returncode}\n输出:\n{output}"

        if not output:
            return "命令执行成功，无终端输出。"

        max_len = 8000
        if len(output) > max_len:
            return f"{output[:max_len]}\n\n...[终端输出过长，已截断至前 {max_len} 字节]..."

        return output


def NewBashTool(work_dir: str | os.PathLike) -> "BashTool":
    return BashTool(work_dir)


def _choose_shell() -> tuple[str, ...]:
    """根据平台选择 Shell。"""
    if _IS_WINDOWS:
        # Windows: 优先 bash (Git/WSL)，否则退回 cmd
        for candidate in ("bash", "git", "wsl"):
            path = _which(candidate)
            if path is not None:
                if candidate == "bash":
                    return (path, "-c")
                if candidate == "git":
                    return (path, "bash", "-c")
                if candidate == "wsl":
                    return (path, "bash", "-c")
        return ("cmd.exe", "/C")
    # Unix-like
    return ("bash", "-c")


def _which(cmd: str) -> str | None:
    """简易 which，避免依赖 shutil.which 之外的环境差异。"""
    import shutil

    return shutil.which(cmd)


__all__ = ["BashTool", "NewBashTool"]