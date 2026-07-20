"""tests.test_compactor: 上下文压缩器的单元测试。"""
from __future__ import annotations

from claw.context.compactor import Compactor, NewCompactor
from claw.schema import Message, RoleSystem, RoleUser, RoleAssistant


class TestCompactor:
    def test_no_compaction_needed(self) -> None:
        compactor = NewCompactor(10000, 3)
        msgs = [
            Message(role=RoleSystem, content="system prompt"),
            Message(role=RoleUser, content="short msg"),
        ]
        result = compactor.compact(msgs)
        assert len(result) == 2
        assert result[0].content == "system prompt"
        assert result[1].content == "short msg"

    def test_system_message_preserved(self) -> None:
        compactor = NewCompactor(10, 1)  # 极低的阈值触发压缩
        msgs = [
            Message(role=RoleSystem, content="I am the system prompt, quite long actually"),
            Message(role=RoleUser, content="hello"),
        ]
        result = compactor.compact(msgs)
        assert result[0].role == RoleSystem
        assert result[0].content == "I am the system prompt, quite long actually"

    def test_working_memory_preserved(self) -> None:
        compactor = NewCompactor(20, 2)
        msgs = [
            Message(role=RoleSystem, content="sys"),
            Message(role=RoleUser, content="old msg 1"),
            Message(role=RoleAssistant, content="old reply 1"),
            Message(role=RoleUser, content="recent msg"),
            Message(role=RoleAssistant, content="recent reply"),
        ]
        result = compactor.compact(msgs)
        # 最近 2 条应保持原样
        assert result[-2].content == "recent msg"
        assert result[-1].content == "recent reply"

    def test_old_tool_output_truncated(self) -> None:
        compactor = NewCompactor(20, 2)
        long_output = "x" * 500
        msgs = [
            Message(role=RoleSystem, content="sys"),
            Message(role=RoleUser, content=long_output, tool_call_id="old_tool"),
            Message(role=RoleUser, content="recent"),
            Message(role=RoleAssistant, content="done"),
        ]
        result = compactor.compact(msgs)
        # 旧工具输出应被截断
        assert "已被系统强制清理" in result[1].content
        assert len(result[1].content) < 300

    def test_old_thinking_folded(self) -> None:
        compactor = NewCompactor(20, 2)
        msgs = [
            Message(role=RoleSystem, content="sys"),
            Message(role=RoleAssistant, content="very long thinking " * 50),
            Message(role=RoleUser, content="recent"),
            Message(role=RoleAssistant, content="done"),
        ]
        result = compactor.compact(msgs)
        assert "已折叠" in result[1].content

    def test_recent_long_tool_output_trimmed(self) -> None:
        compactor = NewCompactor(20, 1)
        long_output = "a" * 2000
        msgs = [
            Message(role=RoleSystem, content="sys"),
            Message(role=RoleUser, content=long_output, tool_call_id="recent_tool"),
        ]
        result = compactor.compact(msgs)
        # 最近的工作记忆中的长输出，前后保留中间截断
        assert "内容过长" in result[1].content

    def test_estimate_length(self) -> None:
        msgs = [
            Message(role=RoleUser, content="hello"),  # 5 chars
            Message(role=RoleAssistant, content="world"),  # 5 chars
        ]
        length = Compactor._estimate_length(msgs)
        assert length == 10
