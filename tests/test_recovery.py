"""tests.test_recovery: 错误恢复管理器的单元测试。"""
from __future__ import annotations

from claw.context.recovery import RecoveryManager, NewRecoveryManager


class TestRecoveryManager:
    def test_edit_file_not_found_hint(self) -> None:
        rm = NewRecoveryManager()
        result = rm.analyze_and_inject(
            "edit_file", "Error: 在文件中未找到 old_text，请检查内容和缩进"
        )
        assert "系统救援指南" in result
        assert "read_file" in result

    def test_edit_file_multiple_matches_hint(self) -> None:
        rm = NewRecoveryManager()
        result = rm.analyze_and_inject(
            "edit_file", "Error: 匹配到了多处，请提供更多上下文"
        )
        assert "系统救援指南" in result
        assert "唯一性" in result

    def test_read_file_not_found_hint(self) -> None:
        rm = NewRecoveryManager()
        result = rm.analyze_and_inject(
            "read_file", "Error: no such file or directory: /tmp/x.txt"
        )
        assert "系统救援指南" in result
        assert "ls -la" in result.lower() or "find" in result.lower()

    def test_write_file_permission_denied_hint(self) -> None:
        rm = NewRecoveryManager()
        result = rm.analyze_and_inject(
            "write_file", "Error: permission denied"
        )
        assert "系统救援指南" in result
        assert "权限" in result

    def test_bash_command_not_found_hint(self) -> None:
        rm = NewRecoveryManager()
        result = rm.analyze_and_inject(
            "bash", "bash: nonexistent: command not found"
        )
        assert "系统救援指南" in result
        assert "替代命令" in result

    def test_bash_timeout_hint(self) -> None:
        rm = NewRecoveryManager()
        result = rm.analyze_and_inject(
            "bash", "命令执行超时"
        )
        assert "系统救援指南" in result
        assert "后台" in result or "nohup" in result

    def test_bash_syntax_error_hint(self) -> None:
        rm = NewRecoveryManager()
        result = rm.analyze_and_inject(
            "bash", "bash: syntax error near unexpected token"
        )
        assert "系统救援指南" in result
        assert "引号" in result

    def test_no_hint_for_unrecognized_error(self) -> None:
        rm = NewRecoveryManager()
        original = "some unknown error message"
        result = rm.analyze_and_inject("bash", original)
        assert result == original  # 不注入提示
