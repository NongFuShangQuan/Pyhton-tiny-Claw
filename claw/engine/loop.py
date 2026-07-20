"""engine.loop: Agent 主循环与子代理循环。

"""
from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

from ..context import (
    Compactor,
    NewCompactor,
    NewPromptComposer,
    NewRecoveryManager,
    Session,
)
from ..observability import (
    AddAttribute,
    EndSpan,
    ExportTraceToFile,
    StartSpan,
    TraceContext,
)
from ..provider import LLMProvider
from ..schema import (
    Message,
    RoleAssistant,
    RoleSystem,
    RoleUser,
    ToolCall,
    ToolResult,
)
from ..tools import Registry
from .reminder import NewReminderInjector
from .reporter import Reporter


_logger = logging.getLogger("claw.engine")


class AgentEngine:
    """ReAct 主循环。

    通过 enable_thinking 切换慢思考阶段；通过 plan_mode 切换状态外部化模式。
    """

    def __init__(
        self,
        provider: LLMProvider,
        registry: Registry,
        enable_thinking: bool = False,
        plan_mode: bool = False,
    ) -> None:
        self.provider = provider
        self.registry = registry
        self.enable_thinking = enable_thinking
        self.plan_mode = plan_mode
        self.compactor: Compactor = NewCompactor(200_000, 6)
        self.recovery = NewRecoveryManager()
        self.injector = NewReminderInjector()

    def run(
        self,
        session: Session,
        reporter: Optional[Reporter] = None,
        ctx: Optional[TraceContext] = None,
    ) -> Optional[Exception]:
        """主循环。返回 None 表示成功，返回 Exception 表示中断原因。"""
        _logger.info(
            "[Engine] 唤醒会话 [%s]，锁定工作区: %s (PlanMode: %s)",
            session.id,
            session.work_dir,
            self.plan_mode,
        )

        ctx, root_span = StartSpan(ctx, "Agent.Run")
        AddAttribute(root_span, "SessionID", session.id)
        AddAttribute(root_span, "WorkDir", session.work_dir)

        try:
            composer = NewPromptComposer(session.work_dir, self.plan_mode)
            system_msg = composer.build()

            turn_count = 0
            while True:
                turn_count += 1
                turn_ctx, turn_span = StartSpan(ctx, f"Turn-{turn_count}")

                available_tools = self.registry.get_available_tools()
                working_memory = session.get_working_memory(20)

                # 截断可能导致首条变成 Assistant；插入占位 User 消息稳住协议
                if working_memory and working_memory[0].role != RoleUser:
                    working_memory = [
                        Message(
                            role=RoleUser,
                            content=(
                                "[系统占位符] 这是为了保持上下文连贯性而注入的断点标记。"
                                "请继续执行你刚才的任务。"
                            ),
                        ),
                        *working_memory,
                    ]

                context_history: list[Message] = [system_msg, *working_memory]
                compacted = self.compactor.compact(context_history)

                AddAttribute(
                    turn_span, "context_message_count", len(compacted)
                )

                current_turn_thinking = ""

                # Phase 1: Thinking
                if self.enable_thinking:
                    if reporter is not None:
                        reporter.on_thinking(turn_ctx)

                    _, think_span = StartSpan(turn_ctx, "LLM.Thinking")
                    try:
                        think_resp = self.provider.generate(compacted, None)
                    except Exception as e:
                        EndSpan(think_span)
                        EndSpan(turn_span)
                        raise RuntimeError(f"Thinking 阶段失败: {e}") from e
                    EndSpan(think_span)

                    if think_resp.content:
                        current_turn_thinking = think_resp.content
                        compacted.append(think_resp)

                # Phase 2: Action
                _, act_span = StartSpan(turn_ctx, "LLM.Action")
                try:
                    action_resp = self.provider.generate(compacted, available_tools)
                except Exception as e:
                    EndSpan(act_span)
                    EndSpan(turn_span)
                    raise RuntimeError(f"Action 阶段失败: {e}") from e
                EndSpan(act_span)

                final_msg = Message(
                    role=RoleAssistant,
                    content=(current_turn_thinking + "\n" + action_resp.content).strip(),
                    tool_calls=list(action_resp.tool_calls),
                )
                session.append(final_msg)

                if action_resp.content and reporter is not None:
                    reporter.on_message(action_resp.content)

                if not action_resp.tool_calls:
                    EndSpan(turn_span)
                    break

                # Phase 3: 并发执行工具
                tool_calls = action_resp.tool_calls
                observations: list[Optional[Message]] = [None] * len(tool_calls)

                # 用于 Reminder 分析的"最后一个工具" - 等价于 idx == 0 的语义
                last_lock = threading.Lock()
                last_tool_call: Optional[ToolCall] = None
                last_tool_result: Optional[ToolResult] = None

                def _run_one(idx: int, call: ToolCall) -> None:
                    nonlocal last_tool_call, last_tool_result

                    if reporter is not None:
                        reporter.on_tool_call(call.name, call.arguments_to_str(), turn_ctx)

                    result = self.registry.execute(turn_ctx, call)

                    final_output = result.output
                    if result.is_error:
                        final_output = self.recovery.analyze_and_inject(call.name, result.output)

                    if reporter is not None:
                        display = final_output
                        if len(display) > 200:
                            display = display[:200] + "... (已截断)"
                        reporter.on_tool_result(call.name, display, result.is_error, turn_ctx)

                    observations[idx] = Message(
                        role=RoleUser,
                        content=final_output,
                        tool_call_id=call.id,
                    )

                    if idx == 0:
                        with last_lock:
                            last_tool_call = call
                            last_tool_result = result

                # 并发执行
                max_workers = max(1, min(len(tool_calls), 8))
                with ThreadPoolExecutor(max_workers=max_workers) as pool:
                    futures = [pool.submit(_run_one, i, tc) for i, tc in enumerate(tool_calls)]
                    for f in futures:
                        # 暴露异常则把异常挂回 observations
                        try:
                            f.result()
                        except Exception as e:  # noqa: BLE001
                            # _run_one 自己已经处理了错误，这里捕获的应是未预期异常
                            _logger.exception("[Engine] 工具执行意外崩溃: %s", e)

                obs_msgs: list[Message] = [m for m in observations if m is not None]
                session.append(*obs_msgs)

                # 死循环探测与注入
                reminder = self.injector.check_and_inject(last_tool_call, last_tool_result)
                if reminder is not None:
                    session.append(reminder)

                EndSpan(turn_span)

            return None
        finally:
            EndSpan(root_span)
            ExportTraceToFile(root_span, session.work_dir, session.id)
            _logger.info(
                "📊 [Tracing] 本次任务的执行回放链路已保存至工作区的 .claw/traces 目录下"
            )

    def run_sub(
        self,
        task_prompt: str,
        read_only_registry: Registry,
        reporter: Optional[Reporter] = None,
        ctx: Optional[TraceContext] = None,
    ) -> "tuple[str, Optional[Exception]]":
        """子代理循环: 一次性、不依赖外部 Session、最多 10 轮。

        实现策略：子代理的 System Prompt 明确警告它必须使用工具，否则盲猜。
          - 一旦不调用工具 = 任务结束，把内容剥离返回。
          - 否则继续执行只读工具的并发循环。
        """
        context_history: list[Message] = [
            Message(
                role=RoleSystem,
                content=(
                    "你是一个专门负责深度探索的探路者 (Explorer Subagent)。\n"
                    "你的任务是根据主架构师的指令，在当前工作区内仔细阅读代码、查阅日志，搜集足够的信息。\n"
                    "【核心纪律】\n"
                    "1. 你必须、且只能依靠内置工具（如 bash 的 find/grep，或 read_file）去寻找答案。"
                    "绝对不允许凭空捏造或猜测！\n"
                    "2. 如果你没有找到确切的答案，你必须继续使用工具深入搜索。\n"
                    "3. 当且仅当你找到了确切的线索后，停止调用工具，直接输出一段纯文本作为你的终极汇报。"
                    "主架构师会根据你的汇报来做下一步决策。"
                ),
            ),
            Message(role=RoleUser, content=task_prompt),
        ]

        max_sub_turns = 10
        turn_count = 0

        while True:
            turn_count += 1
            if turn_count > max_sub_turns:
                return "", RuntimeError(
                    f"子智能体探索过于深入，超过 {max_sub_turns} 轮被强制召回，请主 Agent 给它更明确的指令"
                )

            available_tools = read_only_registry.get_available_tools()
            compacted = self.compactor.compact(context_history)

            # 子任务要求急速响应，绕过慢思考
            try:
                action_resp = self.provider.generate(compacted, available_tools)
            except Exception as e:
                return "", RuntimeError(f"子智能体推理失败: {e}")

            context_history.append(action_resp)

            if not action_resp.tool_calls:
                # 纯文本汇报
                return action_resp.content, None

            # 并发执行只读工具
            observations: list[Optional[Message]] = [None] * len(action_resp.tool_calls)

            def _run_one(idx: int, call: ToolCall) -> None:
                if reporter is not None:
                    reporter.on_tool_call(
                        f"[Subagent] {call.name}", call.arguments_to_str(), ctx
                    )

                result = read_only_registry.execute(ctx, call)

                final_output = result.output
                if result.is_error:
                    final_output = self.recovery.analyze_and_inject(call.name, result.output)

                if reporter is not None:
                    display = final_output
                    if len(display) > 200:
                        display = display[:200] + "... (已截断)"
                    reporter.on_tool_result(
                        f"[Subagent] {call.name}", display, result.is_error, ctx
                    )

                observations[idx] = Message(
                    role=RoleUser,
                    content=final_output,
                    tool_call_id=call.id,
                )

            max_workers = max(1, min(len(action_resp.tool_calls), 8))
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = [
                    pool.submit(_run_one, i, tc)
                    for i, tc in enumerate(action_resp.tool_calls)
                ]
                for f in futures:
                    try:
                        f.result()
                    except Exception as e:  # noqa: BLE001
                        _logger.exception("[Subagent] 工具执行意外崩溃: %s", e)

            obs = [m for m in observations if m is not None]
            context_history.extend(obs)


def NewAgentEngine(
    provider: LLMProvider,
    registry: Registry,
    enable_thinking: bool = False,
    plan_mode: bool = False,
) -> AgentEngine:
    return AgentEngine(provider, registry, enable_thinking, plan_mode)


__all__ = ["AgentEngine", "NewAgentEngine"]