"""tests.test_schema: 消息与工具协议类型的单元测试。"""
from __future__ import annotations

import json

import pytest

from claw.schema import (
    Message,
    RoleAssistant,
    RoleSystem,
    RoleUser,
    ToolCall,
    ToolDefinition,
    ToolResult,
    Usage,
)


class TestUsage:
    def test_default_values(self) -> None:
        u = Usage()
        assert u.prompt_tokens == 0
        assert u.completion_tokens == 0

    def test_custom_values(self) -> None:
        u = Usage(prompt_tokens=100, completion_tokens=50)
        assert u.prompt_tokens == 100
        assert u.completion_tokens == 50


class TestToolCall:
    def test_basic_construction(self) -> None:
        tc = ToolCall(id="call_001", name="read_file", arguments='{"path": "test.py"}')
        assert tc.id == "call_001"
        assert tc.name == "read_file"

    def test_arguments_to_str_with_string(self) -> None:
        tc = ToolCall(id="1", name="bash", arguments='{"command": "ls"}')
        assert tc.arguments_to_str() == '{"command": "ls"}'

    def test_arguments_to_str_with_dict(self) -> None:
        tc = ToolCall(id="1", name="bash", arguments={"command": "ls"})
        result = tc.arguments_to_str()
        assert "command" in result
        assert "ls" in result

    def test_arguments_as_value_with_dict(self) -> None:
        tc = ToolCall(id="1", name="bash", arguments={"command": "ls"})
        val = tc.arguments_as_value()
        assert val == {"command": "ls"}

    def test_arguments_as_value_with_json_string(self) -> None:
        tc = ToolCall(id="1", name="bash", arguments='{"command": "ls"}')
        val = tc.arguments_as_value()
        assert val == {"command": "ls"}

    def test_arguments_to_json_bytes(self) -> None:
        tc = ToolCall(id="1", name="bash", arguments={"command": "ls"})
        result = tc.arguments_to_json_bytes()
        assert isinstance(result, bytes)
        assert b"command" in result

    def test_to_dict(self) -> None:
        tc = ToolCall(id="call_1", name="read_file", arguments={"path": "test.py"})
        d = tc.to_dict()
        assert d["id"] == "call_1"
        assert d["name"] == "read_file"
        assert d["arguments"] == {"path": "test.py"}

    def test_to_dict_with_string_arguments(self) -> None:
        tc = ToolCall(id="call_1", name="bash", arguments='{"command": "ls"}')
        d = tc.to_dict()
        assert d["arguments"] == {"command": "ls"}

    def test_arguments_to_str_with_bytes(self) -> None:
        tc = ToolCall(id="1", name="bash", arguments=b'{"command": "ls"}')
        result = tc.arguments_to_str()
        assert "command" in result


class TestMessage:
    def test_user_message(self) -> None:
        msg = Message(role=RoleUser, content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.tool_calls == []
        assert msg.tool_call_id == ""

    def test_assistant_message_with_tool_calls(self) -> None:
        tc = ToolCall(id="1", name="bash", arguments='{"command": "ls"}')
        msg = Message(role=RoleAssistant, content="Let me check", tool_calls=[tc])
        assert len(msg.tool_calls) == 1
        assert msg.tool_calls[0].name == "bash"

    def test_tool_result_message(self) -> None:
        msg = Message(role=RoleUser, content="file content", tool_call_id="call_1")
        assert msg.tool_call_id == "call_1"

    def test_to_dict_basic(self) -> None:
        msg = Message(role=RoleSystem, content="You are helpful")
        d = msg.to_dict()
        assert d["role"] == "system"
        assert d["content"] == "You are helpful"

    def test_to_dict_with_usage(self) -> None:
        msg = Message(role=RoleAssistant, content="Hi", usage=Usage(10, 5))
        d = msg.to_dict()
        assert d["usage"]["prompt_tokens"] == 10
        assert d["usage"]["completion_tokens"] == 5


class TestToolResult:
    def test_success_result(self) -> None:
        tr = ToolResult(tool_call_id="1", output="done")
        assert tr.is_error is False

    def test_error_result(self) -> None:
        tr = ToolResult(tool_call_id="1", output="fail", is_error=True)
        assert tr.is_error is True


class TestToolDefinition:
    def test_to_dict(self) -> None:
        td = ToolDefinition(
            name="bash",
            description="Run commands",
            input_schema={
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        )
        d = td.to_dict()
        assert d["name"] == "bash"
        assert d["input_schema"]["required"] == ["command"]

    def test_json_roundtrip(self) -> None:
        td = ToolDefinition(
            name="read_file",
            description="Read a file",
            input_schema={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        )
        data = json.dumps(td.to_dict())
        restored = json.loads(data)
        assert restored["name"] == "read_file"
        assert restored["input_schema"]["required"] == ["path"]
