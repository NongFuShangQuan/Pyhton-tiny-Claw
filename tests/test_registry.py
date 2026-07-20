"""tests.test_registry: 工具注册中心与中间件链的单元测试。"""
from __future__ import annotations

from typing import Any

import pytest

from claw.schema import ToolCall, ToolDefinition
from claw.tools._args import parse_args
from claw.tools.registry import (
    BaseTool,
    NewRegistry,
    Registry,
    RegistryImpl,
)


class _MockTool(BaseTool):
    """测试用 Mock 工具。"""

    def __init__(self, name: str = "mock", output: str = "mock output"):
        self._name = name
        self._output = output
        self.execute_calls: list[Any] = []

    def name(self) -> str:
        return self._name

    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self._name,
            description="A mock tool for testing",
            input_schema={
                "type": "object",
                "properties": {"arg": {"type": "string"}},
                "required": ["arg"],
            },
        )

    def execute(self, args: Any) -> str:
        self.execute_calls.append(args)
        return self._output


class _FailingTool(BaseTool):
    def name(self) -> str:
        return "failing"

    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="failing",
            description="Always fails",
            input_schema={"type": "object", "properties": {}},
        )

    def execute(self, args: Any) -> str:
        raise RuntimeError("tool always fails")


class TestRegistry:
    def test_register_and_get_tools(self) -> None:
        registry = NewRegistry()
        tool = _MockTool("test_tool")
        registry.register(tool)

        tools = registry.get_available_tools()
        assert len(tools) == 1
        assert tools[0].name == "test_tool"

    def test_execute_registered_tool(self) -> None:
        registry = NewRegistry()
        tool = _MockTool("greet", "hello!")
        registry.register(tool)

        call = ToolCall(id="1", name="greet", arguments={"arg": "world"})
        result = registry.execute(None, call)

        assert result.is_error is False
        assert result.output == "hello!"
        assert len(tool.execute_calls) == 1

    def test_execute_unknown_tool(self) -> None:
        registry = NewRegistry()
        call = ToolCall(id="1", name="nonexistent", arguments={})
        result = registry.execute(None, call)
        assert result.is_error is True
        assert "不存在" in result.output

    def test_execute_failing_tool(self) -> None:
        registry = NewRegistry()
        registry.register(_FailingTool())
        call = ToolCall(id="1", name="failing", arguments={})
        result = registry.execute(None, call)
        assert result.is_error is True
        assert "Error executing" in result.output

    def test_duplicate_tool_warns(self) -> None:
        registry = NewRegistry()
        registry.register(_MockTool("same_name", "first"))
        registry.register(_MockTool("same_name", "second"))
        # 注册相同名称不会报错，但会覆盖
        tools = registry.get_available_tools()
        assert len(tools) == 1

    def test_middleware_chain_intercept(self) -> None:
        registry = NewRegistry()
        tool = _MockTool("protected")
        registry.register(tool)

        # 添加拦截中间件
        registry.use(lambda call: (False, "blocked by policy"))
        call = ToolCall(id="1", name="protected", arguments={})
        result = registry.execute(None, call)
        assert result.is_error is True
        assert "被系统拦截" in result.output

    def test_middleware_chain_allow(self) -> None:
        registry = NewRegistry()
        tool = _MockTool("allowed", "success")
        registry.register(tool)

        registry.use(lambda call: (True, ""))
        call = ToolCall(id="1", name="allowed", arguments={})
        result = registry.execute(None, call)
        assert result.is_error is False
        assert result.output == "success"

    def test_multiple_middlewares_first_blocks(self) -> None:
        registry = NewRegistry()
        tool = _MockTool("blocked_early")
        registry.register(tool)

        call_count = []

        def mw1(call: ToolCall):
            call_count.append("mw1")
            return False, "blocked by first"

        def mw2(call: ToolCall):
            call_count.append("mw2")
            return True, ""

        registry.use(mw1)
        registry.use(mw2)

        call = ToolCall(id="1", name="blocked_early", arguments={})
        result = registry.execute(None, call)
        assert result.is_error is True
        assert call_count == ["mw1"]  # mw2 未被调用


class TestParseArgs:
    def test_dict_passthrough(self) -> None:
        assert parse_args({"key": "value"}) == {"key": "value"}

    def test_valid_json_string(self) -> None:
        assert parse_args('{"key": "value"}') == {"key": "value"}

    def test_valid_json_bytes(self) -> None:
        assert parse_args(b'{"key": "value"}') == {"key": "value"}

    def test_invalid_json_string(self) -> None:
        assert parse_args("not json") is None

    def test_invalid_json_bytes(self) -> None:
        assert parse_args(b"not json") is None

    def test_unexpected_type(self) -> None:
        assert parse_args(42) is None  # type: ignore
        assert parse_args(None) is None  # type: ignore
