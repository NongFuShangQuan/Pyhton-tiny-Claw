"""claw.cli.app: 交互式 REPL 命令行界面。

提供类似 Claude Code 的交互体验：
- 默认启动交互模式，读取用户输入并逐轮驱动 Agent 引擎
- 支持斜杠命令管理会话、切换模型、查看消耗等
- 使用 rich 库提供彩色终端输出
"""
from __future__ import annotations

import atexit
import time
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table
from rich.rule import Rule

from claw.context import GlobalSessionMgr, Session
from claw.engine import AgentEngine, NewAgentEngine, Reporter
from claw.factory import build_registry, create_provider
from claw.observability import (
    AddAttribute,
    EndSpan,
    ExportTraceToFile,
    StartSpan,
    TraceContext,
)
from claw.observability.tracker import CostTracker, NewCostTracker
from claw.provider import LLMProvider
from claw.schema import Message, RoleUser


class RichReporter(Reporter):
    """使用 rich 格式化的终端 Reporter。"""

    def __init__(self, console: Console):
        self.console = console

    def on_thinking(self, ctx=None) -> None:
        self.console.print()
        self.console.print(
            Panel("模型正在深度推理中...", style="dim", border_style="yellow")
        )

    def on_tool_call(self, tool_name: str, args: str, ctx=None) -> None:
        display_args = args.replace("\n", "\\n").replace("\r", "\\r")
        if len(display_args) > 200:
            display_args = display_args[:200] + "..."
        self.console.print(
            f"  [bold cyan]◉[/bold cyan] [cyan]{tool_name}[/cyan]  "
            f"[dim]{display_args}[/dim]"
        )

    def on_tool_result(
        self, tool_name: str, result: str, is_error: bool, ctx=None
    ) -> None:
        prefix = "  [bold red]✗[/bold red]" if is_error else "  [bold green]✓[/bold green]"
        display = result
        if len(display) > 300:
            display = display[:300] + "\n... (输出已截断)"
        self.console.print(f"{prefix} [dim]{tool_name}[/dim]")

    def on_message(self, content: str, ctx=None) -> None:
        if not content:
            return
        self.console.print()
        self.console.print(
            Panel(
                Markdown(content),
                title="Agent 回复",
                title_align="left",
                border_style="green",
            )
        )


class InteractiveCLI:
    """交互式 CLI 主控。

    使用方式：
        cli = InteractiveCLI()
        raise SystemExit(cli.run())
    """

    WELCOME = """[bold cyan]py-tiny-claw[/bold cyan] — 极简 AI Agent 驾驭引擎

交互模式已启动。输入任务描述驱动 Agent，或使用 [yellow]/help[/yellow] 查看命令。
输入 [yellow]/exit[/yellow] 或 Ctrl+C 退出。"""

    PROMPT = "[bold green]>[/bold green] "

    def __init__(
        self,
        work_dir: str = ".",
        provider: str = "deepseek",
        model: str = "deepseek-v4-flash",
        thinking: bool = False,
        plan_mode: bool = True,
        session_id: Optional[str] = None,
    ):
        self.console = Console()
        self.work_dir = Path(work_dir).resolve()
        self.provider_name = provider
        self.model_name = model
        self.enable_thinking = thinking
        self.plan_mode = plan_mode

        self._provider: Optional[LLMProvider] = None
        self._engine: Optional[AgentEngine] = None
        self._session: Optional[Session] = None
        self._reporter = RichReporter(self.console)
        self._running = True

        if session_id is None:
            session_id = f"cli_interactive_{int(time.time())}"
        self._session_id = session_id

        self._init_provider()
        self._init_session()
        self._init_engine()

        atexit.register(self._save_history)

    # ── 初始化 ──────────────────────────────────────────────

    def _init_provider(self) -> None:
        """创建底层 LLM Provider。"""
        self._provider = create_provider(self.provider_name, self.model_name)
        self._provider = NewCostTracker(self._provider, self.model_name)

    def _init_session(self) -> None:
        """获取或创建 Session。"""
        self._session = GlobalSessionMgr.get_or_create(
            self._session_id, str(self.work_dir)
        )
        if isinstance(self._provider, CostTracker):
            self._provider._session = self._session

    def _init_engine(self) -> None:
        """创建 Agent 引擎与工具注册表。"""
        registry = build_registry(self.work_dir)
        self._engine = NewAgentEngine(
            self._provider,
            registry,
            enable_thinking=self.enable_thinking,
            plan_mode=self.plan_mode,
        )

    # ── History ─────────────────────────────────────────────

    def _setup_history(self) -> None:
        """初始化 readline 历史记录。"""
        try:
            import readline
        except ImportError:
            return

        hist_file = Path.home() / ".claw_history"
        try:
            readline.read_history_file(str(hist_file))
        except (FileNotFoundError, OSError):
            pass

        readline.set_history_length(1000)

    def _save_history(self) -> None:
        """保存 readline 历史。"""
        try:
            import readline

            hist_file = Path.home() / ".claw_history"
            readline.write_history_file(str(hist_file))
        except (ImportError, OSError):
            pass

    # ── 主循环 ──────────────────────────────────────────────

    def run(self) -> int:
        """启动 REPL，返回进程退出码。"""
        self._setup_history()

        self.console.print(Rule(style="cyan"))
        self.console.print(self.WELCOME)
        self.console.print(Rule(style="cyan"))
        self._print_status_line()

        while self._running:
            try:
                line = self._read_input()
            except (KeyboardInterrupt, EOFError):
                self.console.print("\n[yellow]正在退出...[/yellow]")
                break

            stripped = line.strip()
            if not stripped:
                continue

            if stripped.startswith("/"):
                self._handle_command(stripped)
            else:
                self._handle_task(stripped)

        self.console.print(self._format_status())
        return 0

    def _read_input(self) -> str:
        """读取一行用户输入；支持反斜杠续行。"""
        try:
            first = self.console.input(self.PROMPT)
        except (KeyboardInterrupt, EOFError):
            raise

        if not first.rstrip().endswith("\\"):
            return first

        # 多行续行模式
        lines = [first.rstrip()[:-1]]  # 去掉末尾反斜杠
        continuation = "[dim]. . . [/dim]"
        while True:
            try:
                nxt = self.console.input(continuation)
            except (KeyboardInterrupt, EOFError):
                raise

            if nxt.rstrip().endswith("\\"):
                lines.append(nxt.rstrip()[:-1])
            else:
                lines.append(nxt)
                break
        return "\n".join(lines)

    # ── 任务执行 ────────────────────────────────────────────

    def _handle_task(self, prompt: str) -> None:
        """将用户输入作为任务推送给 Agent 引擎。"""
        self.console.print(
            f"\n[dim]任务: {prompt[:100]}{'...' if len(prompt) > 100 else ''}[/dim]\n"
        )

        ctx, root_span = StartSpan(TraceContext(), "CLI.Interactive")
        AddAttribute(root_span, "Prompt", prompt)

        self._session.append(Message(role=RoleUser, content=prompt))

        start_time = time.time()
        try:
            err = self._engine.run(self._session, self._reporter, ctx=ctx)
        except Exception as exc:
            self.console.print(
                f"\n[bold red]引擎运行异常: {exc}[/bold red]"
            )
            err = exc

        EndSpan(root_span)
        ExportTraceToFile(root_span, str(self.work_dir), self._session.id)

        elapsed = time.time() - start_time
        if err is not None:
            self.console.print(f"\n[bold red]任务执行失败: {err}[/bold red]")
        else:
            self.console.print(
                f"\n[dim]完成 | 耗时 {elapsed:.1f}s | "
                f"累计消耗 ¥{self._session.total_cost_cny:.6f}[/dim]"
            )

    # ── 斜杠命令 ────────────────────────────────────────────

    def _handle_command(self, raw: str) -> None:
        """解析并执行斜杠命令。"""
        parts = raw.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        handlers = {
            "/help": self._cmd_help,
            "/h": self._cmd_help,
            "/exit": self._cmd_exit,
            "/quit": self._cmd_exit,
            "/q": self._cmd_exit,
            "/clear": self._cmd_clear,
            "/model": lambda a: self._cmd_model(a),
            "/thinking": lambda a: self._cmd_toggle_thinking(),
            "/plan": lambda a: self._cmd_toggle_plan(),
            "/session": lambda a: self._cmd_session(a),
            "/cost": lambda a: self._cmd_cost(),
            "/status": lambda a: self._print_status_line(),
            "/dir": lambda a: self._cmd_dir(a),
            "/provider": lambda a: self._cmd_provider(a),
            "/workdir": lambda a: self._cmd_dir(a),
        }

        handler = handlers.get(cmd)
        if handler is None:
            self.console.print(
                f"[red]未知命令: {cmd}[/red]。输入 [yellow]/help[/yellow] 查看可用命令。"
            )
            return

        try:
            handler(arg)
        except Exception as exc:
            self.console.print(f"[red]命令执行失败: {exc}[/red]")

    def _cmd_help(self, _arg: str) -> None:
        """显示帮助。"""
        help_text = """[bold cyan]py-tiny-claw 交互模式命令[/bold cyan]

[bold]基础操作[/bold]
  [yellow]/help, /h[/yellow]        显示此帮助
  [yellow]/exit, /quit, /q[/yellow] 退出程序
  [yellow]/clear[/yellow]           清空当前会话历史（开新会话）

[bold]会话管理[/bold]
  [yellow]/session [id][/yellow]    显示或切换会话 ID
  [yellow]/status[/yellow]          显示当前状态

[bold]模型与配置[/bold]
  [yellow]/model <name>[/yellow]    切换模型（需重建引擎）
  [yellow]/provider <name>[/yellow] 切换 Provider (deepseek / zhipu)
  [yellow]/thinking[/yellow]        开关慢思考模式
  [yellow]/plan[/yellow]            开关 Plan Mode
  [yellow]/dir [path][/yellow]      显示或更改工作区路径

[bold]费用[/bold]
  [yellow]/cost[/yellow]            查看当前会话 Token 与费用

[bold]使用提示[/bold]
  直接输入任务描述即可驱动 Agent 执行。
  行尾加 [dim]\\\\[/dim] 可续行输入多行内容。
  按 Ctrl+C 退出程序。"""
        self.console.print(Panel(Markdown(help_text), border_style="cyan"))

    def _cmd_exit(self, _arg: str) -> None:
        """退出程序。"""
        self._running = False

    def _cmd_clear(self, _arg: str) -> None:
        """清除当前会话，创建新会话。"""
        old_id = self._session_id
        self._session_id = f"cli_interactive_{int(time.time())}"
        self._init_session()
        self.console.print(
            f"[green]✓[/green] 会话已重置: [dim]{old_id}[/dim] → [bold]{self._session_id}[/bold]"
        )

    def _cmd_model(self, arg: str) -> None:
        """切换模型。"""
        if not arg.strip():
            self.console.print(f"当前模型: [cyan]{self.model_name}[/cyan]")
            return
        self.model_name = arg.strip()
        self._init_provider()
        self._init_engine()
        self.console.print(f"[green]✓[/green] 模型已切换至: [cyan]{self.model_name}[/cyan]")

    def _cmd_toggle_thinking(self) -> None:
        """开关慢思考模式。"""
        self.enable_thinking = not self.enable_thinking
        self._init_engine()
        state = "[green]开启[/green]" if self.enable_thinking else "[red]关闭[/red]"
        self.console.print(f"慢思考模式: {state}")

    def _cmd_toggle_plan(self) -> None:
        """开关 Plan Mode。"""
        self.plan_mode = not self.plan_mode
        self._init_engine()
        state = "[green]开启[/green]" if self.plan_mode else "[red]关闭[/red]"
        self.console.print(f"Plan Mode: {state}")

    def _cmd_session(self, arg: str) -> None:
        """显示或切换会话。"""
        if not arg.strip():
            self.console.print(f"当前会话: [cyan]{self._session_id}[/cyan]")
            return
        self._session_id = arg.strip()
        self._init_session()
        self.console.print(f"[green]✓[/green] 已切换到会话: [cyan]{self._session_id}[/cyan]")

    def _cmd_cost(self) -> None:
        """显示费用统计。"""
        self.console.print(self._format_cost_table())

    def _cmd_dir(self, arg: str) -> None:
        """显示或切换工作区。"""
        if not arg.strip():
            self.console.print(f"当前工作区: [cyan]{self.work_dir}[/cyan]")
            return
        new_dir = Path(arg.strip()).resolve()
        if not new_dir.exists():
            self.console.print(f"[red]目录不存在: {new_dir}[/red]")
            return
        self.work_dir = new_dir
        self._init_session()
        self._init_engine()
        self.console.print(f"[green]✓[/green] 工作区已切换至: [cyan]{self.work_dir}[/cyan]")

    def _cmd_provider(self, arg: str) -> None:
        """切换 LLM Provider。"""
        valid = ("deepseek", "zhipu")
        if not arg.strip():
            self.console.print(
                f"当前 Provider: [cyan]{self.provider_name}[/cyan] (可选: {', '.join(valid)})"
            )
            return
        choice = arg.strip().lower()
        if choice not in valid:
            self.console.print(f"[red]无效 Provider: {choice}[/red]。可选: {', '.join(valid)}")
            return
        self.provider_name = choice
        self._init_provider()
        self._init_engine()
        self.console.print(f"[green]✓[/green] Provider 已切换至: [cyan]{self.provider_name}[/cyan]")

    # ── 状态显示 ────────────────────────────────────────────

    def _print_status_line(self) -> None:
        """输出一行紧凑状态。"""
        self.console.print(self._format_status())

    def _format_status(self) -> str:
        """格式化状态行。"""
        parts = [
            f"会话: [cyan]{self._session_id}[/cyan]",
            f"模型: [cyan]{self.model_name}[/cyan]",
            f"Provider: [cyan]{self.provider_name}[/cyan]",
        ]
        if self.enable_thinking:
            parts.append("思考: [green]ON[/green]")
        if self.plan_mode:
            parts.append("Plan: [green]ON[/green]")
        if self._session is not None:
            parts.append(f"累计: [yellow]¥{self._session.total_cost_cny:.6f}[/yellow]")
        return "  |  ".join(parts)

    def _format_cost_table(self) -> Table:
        """格式化费用表格。"""
        table = Table(title="当前会话消耗统计")
        table.add_column("指标", style="cyan")
        table.add_column("数值", style="yellow")

        if self._session is not None:
            table.add_row("Prompt Tokens", f"{self._session.total_prompt_tokens:,}")
            table.add_row("Completion Tokens", f"{self._session.total_completion_tokens:,}")
            total_tokens = (
                self._session.total_prompt_tokens + self._session.total_completion_tokens
            )
            table.add_row("Total Tokens", f"{total_tokens:,}")
            table.add_row("累计费用 (CNY)", f"¥{self._session.total_cost_cny:.6f}")
        else:
            table.add_row("状态", "无活动会话")

        return table


def run_interactive(
    work_dir: str = ".",
    provider: str = "deepseek",
    model: str = "deepseek-v4-flash",
    thinking: bool = False,
    plan_mode: bool = True,
    session_id: Optional[str] = None,
) -> int:
    """便捷函数：启动交互式 CLI 并返回退出码。"""
    cli = InteractiveCLI(
        work_dir=work_dir,
        provider=provider,
        model=model,
        thinking=thinking,
        plan_mode=plan_mode,
        session_id=session_id,
    )
    return cli.run()


__all__ = ["InteractiveCLI", "RichReporter", "run_interactive"]
