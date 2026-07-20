"""tests.test_reminder: 死循环探测器的单元测试。"""
from __future__ import annotations

from claw.engine.reminder import ReminderInjector, NewReminderInjector
from claw.schema import ToolCall, ToolResult


class TestReminderInjector:
    def test_no_intervention_on_success(self) -> None:
        injector = NewReminderInjector()
        call = ToolCall(id="1", name="bash", arguments='{"command": "ls"}')
        result = ToolResult(tool_call_id="1", output="file1\nfile2", is_error=False)
        msg = injector.check_and_inject(call, result)
        assert msg is None

    def test_no_intervention_on_none_inputs(self) -> None:
        injector = NewReminderInjector()
        assert injector.check_and_inject(None, None) is None
        call = ToolCall(id="1", name="bash", arguments="{}")
        assert injector.check_and_inject(call, None) is None

    def test_first_failure_no_intervention(self) -> None:
        injector = NewReminderInjector()
        call = ToolCall(id="1", name="bash", arguments='{"command": "invalid_cmd"}')
        result = ToolResult(tool_call_id="1", output="command not found", is_error=True)
        msg = injector.check_and_inject(call, result)
        assert msg is None  # 第一次失败不注入

    def test_second_failure_no_intervention(self) -> None:
        injector = NewReminderInjector()
        call = ToolCall(id="1", name="bash", arguments='{"command": "invalid_cmd"}')
        result = ToolResult(tool_call_id="1", output="command not found", is_error=True)
        injector.check_and_inject(call, result)
        msg = injector.check_and_inject(call, result)
        assert msg is None  # 第二次失败仍不注入

    def test_third_failure_triggers_intervention(self) -> None:
        injector = NewReminderInjector()
        call = ToolCall(id="1", name="bash", arguments='{"command": "invalid"}')
        result = ToolResult(tool_call_id="1", output="command not found", is_error=True)
        injector.check_and_inject(call, result)
        injector.check_and_inject(call, result)
        msg = injector.check_and_inject(call, result)
        assert msg is not None
        assert "死循环" in msg.content
        assert "bash" in msg.content

    def test_success_resets_failure_count(self) -> None:
        injector = NewReminderInjector()
        bad_call = ToolCall(id="1", name="bash", arguments='{"command": "bad"}')
        bad_result = ToolResult(tool_call_id="1", output="error", is_error=True)

        injector.check_and_inject(bad_call, bad_result)
        injector.check_and_inject(bad_call, bad_result)

        # 中间成功一次
        good_call = ToolCall(id="2", name="bash", arguments='{"command": "ls"}')
        good_result = ToolResult(tool_call_id="2", output="ok", is_error=False)
        injector.check_and_inject(good_call, good_result)

        # 再次失败应该重新计数
        msg = injector.check_and_inject(bad_call, bad_result)
        assert msg is None  # 计数器被重置了

    def test_different_tools_independent(self) -> None:
        injector = NewReminderInjector()
        call_a = ToolCall(id="1", name="bash", arguments='{"command": "bad1"}')
        call_b = ToolCall(id="2", name="read_file", arguments='{"path": "nonexistent"}')
        result_a = ToolResult(tool_call_id="1", output="error", is_error=True)
        result_b = ToolResult(tool_call_id="2", output="error", is_error=True)

        injector.check_and_inject(call_a, result_a)
        injector.check_and_inject(call_a, result_a)
        injector.check_and_inject(call_b, result_b)  # 不同工具/参数
        msg = injector.check_and_inject(call_a, result_a)  # call_a 第3次
        assert msg is not None  # call_a 触发注入
