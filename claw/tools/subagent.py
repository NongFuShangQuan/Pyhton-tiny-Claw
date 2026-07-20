"""tools.subagent: 子代理委派工具 (探路者 Subagent)。

对应 Go 版 internal/tools/subagent.go。
"""
from __future__ import annotations

import logging
from typing import Any, Optional, Protocol, runtime_checkable

from ..schema import ToolDefinition
from ._args import parse_args
from .registry import BaseTool, Registry


_logger = logging.getLogger("claw.subagent")


@runtime_checkable
class AgentRunner(Protocol):
    """引擎向外部工具暴露的子代理运行能力接口。

    Protocol 签名与 engine.AgentEngine.run_sub 保持一致。
    """

    def run_sub(
        self,
        task_prompt: str,
        read_only_registry: Registry,
        reporter: Any = None,
        ctx: Any = None,
    ) -> "tuple[str, Optional[Exception]]":
        """返回 (summary, error)。"""
        ...


class SubagentTool(BaseTool):
    def __init__(
        self,
        runner: AgentRunner,
        read_only_registry: Registry,
        reporter: Any = None,
    ):
        self._runner = runner
        self._read_only_registry = read_only_registry
        self._reporter = reporter

    def name(self) -> str:
        return "spawn_subagent"

    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name(),
            description="派出一个专门用于深度探索（Exploration）的子智能体。当你需要阅读大量代码、跨文件查找逻辑时请调用此工具。它在探索完毕后，会给你返回一份极度精炼的摘要报告。",
            input_schema={
                "type": "object",
                "properties": {
                    "task_prompt": {
                        "type": "string",
                        "description": "给子智能体下达的明确探索指令。",
                    },
                },
                "required": ["task_prompt"],
            },
        )

    def execute(self, args: Any) -> str:
        input_data = parse_args(args)
        if input_data is None:
            return "Error: 解析参数失败: 非法 JSON"
        task_prompt = input_data.get("task_prompt", "")
        if not task_prompt:
            return "Error: 缺少 task_prompt 参数"

        _logger.info("[Subagent] 🚀 主 Agent 发起委派！正在拉起探路者: [%s]...", task_prompt)

        try:
            summary, err = self._runner.run_sub(
                task_prompt, self._read_only_registry, self._reporter
            )
        except Exception as e:
            # 等价于 Go 版 err != nil 时返回的 error，但 Python 这里直接拼装
            return f"Error: 子智能体执行失败: {e}"

        if err is not None:
            return f"Error: 子智能体执行失败: {err}"

        _logger.info("[Subagent] ✅ 子智能体任务结束。报告返回给主干...")

        return f"【子智能体探索报告】:\n{summary}"


def NewSubagentTool(
    runner: AgentRunner, read_only_registry: Registry, reporter: Any = None
) -> "SubagentTool":
    return SubagentTool(runner, read_only_registry, reporter)


__all__ = ["SubagentTool", "AgentRunner", "NewSubagentTool"]