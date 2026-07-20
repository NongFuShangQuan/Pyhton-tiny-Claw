"""engine.terminal_reporter: 彩色终端 Reporter。

"""
from __future__ import annotations

from typing import Any, Optional

from .reporter import Reporter


class TerminalReporter(Reporter):
    """终端 Reporter，优先使用 rich 渲染，无 rich 时退化为纯文本。"""

    def __init__(self):
        self._console = None
        self._has_rich = False
        try:
            from rich.console import Console
            self._console = Console()
            self._has_rich = True
        except ImportError:
            pass

    def on_thinking(self, ctx: Optional[Any] = None) -> None:
        if self._has_rich:
            from rich.panel import Panel
            self._console.print()
            self._console.print(
                Panel("模型正在深度推理中...", style="dim", border_style="yellow")
            )
        else:
            print("\n[🤔 思考中] 模型正在推理...\n")

    def on_tool_call(
        self,
        tool_name: str,
        args: str,
        ctx: Optional[Any] = None,
    ) -> None:
        display = args.replace("\n", "\\n").replace("\r", "\\r")
        if len(display) > 150:
            display = display[:150] + "... (已截断)"

        if self._has_rich:
            self._console.print(
                f"  [bold cyan]◉[/bold cyan] [cyan]{tool_name}[/cyan]  "
                f"[dim]{display}[/dim]"
            )
        else:
            print(f"[🛠️ 调用工具] {tool_name}")
            print(f"   参数: {display}")

    def on_tool_result(
        self,
        tool_name: str,
        result: str,
        is_error: bool,
        ctx: Optional[Any] = None,
    ) -> None:
        if is_error:
            if self._has_rich:
                self._console.print(
                    f"  [bold red]✗[/bold red] [dim]{tool_name}[/dim]"
                )
                if result:
                    self._console.print(f"    [red]{result[:300]}[/red]")
            else:
                print(f"[❌ 执行失败] {tool_name}")
                if result:
                    print(f"   错误: {result}")
        else:
            if self._has_rich:
                self._console.print(
                    f"  [bold green]✓[/bold green] [dim]{tool_name}[/dim]"
                )
            else:
                print(f"[✅ 执行成功] {tool_name}")

    def on_message(self, content: str, ctx: Optional[Any] = None) -> None:
        if not content:
            return
        if self._has_rich:
            from rich.panel import Panel
            from rich.markdown import Markdown
            self._console.print()
            self._console.print(
                Panel(
                    Markdown(content),
                    title="Agent 回复",
                    title_align="left",
                    border_style="green",
                )
            )
        else:
            print(f"\n🤖 Agent 回复:\n{content}\n")


def NewTerminalReporter() -> TerminalReporter:
    return TerminalReporter()


__all__ = ["TerminalReporter", "NewTerminalReporter"]
