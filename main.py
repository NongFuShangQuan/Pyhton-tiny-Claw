"""claw CLI: 交互式 AI Agent 命令行界面。

用法:
    claw                          # 默认启动交互模式 (REPL)
    claw --prompt "任务描述"       # 一次性任务执行模式

需要设置环境变量:
    DEEPSEEK_API_KEY: DeepSeek API Key (默认)
    ZHIPU_API_KEY: 智谱 API Key
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path


def _get_app_dir() -> Path:
    """获取应用根目录（兼容 PyInstaller 打包后的 exe 路径）。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


_APP_DIR = _get_app_dir()
sys.path.insert(0, str(_APP_DIR))

from dotenv import load_dotenv

# 按优先级加载 .env：exe 同级目录 > 用户主目录
_env_path = _APP_DIR / ".env"
if not _env_path.exists():
    _env_path = Path.home() / ".claw.env"
load_dotenv(_env_path)

from claw.cli.app import InteractiveCLI
from claw.context import GlobalSessionMgr
from claw.engine import NewAgentEngine, NewTerminalReporter
from claw.factory import build_registry, create_provider
from claw.observability import (
    AddAttribute,
    EndSpan,
    ExportTraceToFile,
    StartSpan,
    TraceContext,
)
from claw.observability.tracker import NewCostTracker
from claw.schema import Message, RoleUser


def run_one_shot(args: argparse.Namespace) -> int:
    """一次性任务执行模式（原有行为）。"""
    work_dir = Path(args.dir).resolve()

    print("==================================================")
    print("🚀 启动 go-tiny-claw CLI 引擎...")
    print(f"📁 锁定工作区: {work_dir}")
    print(f"🧠 Provider: {args.provider} | 模型: {args.model}")
    print("==================================================")

    try:
        real_provider = create_provider(args.provider, args.model)
    except Exception as e:
        print(f"❌ Provider 初始化失败: {e}", file=sys.stderr)
        return 2

    sess = GlobalSessionMgr.get_or_create(args.session, str(work_dir))
    tracked_provider = NewCostTracker(real_provider, args.model, sess)
    registry = build_registry(work_dir)

    plan_mode = not args.no_plan
    eng = NewAgentEngine(
        tracked_provider,
        registry,
        enable_thinking=args.thinking,
        plan_mode=plan_mode,
    )

    ctx, root_span = StartSpan(TraceContext(), "CLI.TaskRun")
    AddAttribute(root_span, "Prompt", args.prompt)

    reporter = NewTerminalReporter()

    print(f"\n🎯 收到任务: {args.prompt}\n")

    sess.append(Message(role=RoleUser, content=args.prompt))

    start_time = time.time()
    err = eng.run(sess, reporter, ctx=ctx)
    EndSpan(root_span)
    ExportTraceToFile(root_span, str(work_dir), sess.id)

    if err is not None:
        print(f"\n💥 引擎运行崩溃: {err}", file=sys.stderr)
        return 1

    elapsed = time.time() - start_time
    print("\n==================================================")
    print(f"✨ 任务圆满结束。总耗时: {elapsed:.2f}s")
    print(
        f"💰 Session 累计消耗: ${sess.total_cost_cny:.6f} | "
        f"Token: Input {sess.total_prompt_tokens}, Output {sess.total_completion_tokens}"
    )
    print("==================================================")
    return 0


def run_interactive_cli(args: argparse.Namespace) -> int:
    """交互式 REPL 模式。"""
    return InteractiveCLI(
        work_dir=str(Path(args.dir).resolve()),
        provider=args.provider,
        model=args.model,
        thinking=args.thinking,
        plan_mode=not args.no_plan,
        session_id=args.session if args.session != "cli_default_session" else None,
    ).run()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="py-tiny-claw — 极简 AI Agent 驾驭引擎",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例:
  claw                             交互模式 (默认)
  claw --prompt "创建 hello.py"   一次性任务模式
  claw --thinking --no-plan       以慢思考+无计划模式启动交互""",
    )
    parser.add_argument(
        "--prompt",
        default=None,
        help="要交给 Agent 执行的任务描述。不提供则进入交互模式。",
    )
    parser.add_argument(
        "--dir",
        default=".",
        help="Agent 运行的工作区目录路径 (默认为当前目录)",
    )
    parser.add_argument(
        "--session",
        default="cli_default_session",
        help="指定会话 ID，支持断点续传",
    )
    parser.add_argument(
        "--thinking",
        action="store_true",
        help="开启慢思考阶段 (默认关闭)",
    )
    parser.add_argument(
        "--no-plan",
        action="store_true",
        help="关闭 Plan Mode (默认开启)",
    )
    parser.add_argument(
        "--model",
        default="deepseek-v4-flash",
        help="使用的模型名称，默认 deepseek-v4-flash",
    )
    parser.add_argument(
        "--provider",
        default="deepseek",
        choices=["zhipu", "deepseek"],
        help="LLM Provider 选择，默认 deepseek",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.prompt is not None:
        return run_one_shot(args)
    else:
        return run_interactive_cli(args)


if __name__ == "__main__":
    raise SystemExit(main())
