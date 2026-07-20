"""tests.test_edit_file: fuzzy_replace 四级模糊匹配的单元测试。"""
from __future__ import annotations

import pytest

from claw.tools.edit_file import fuzzy_replace, line_by_line_replace


class TestFuzzyReplace:
    """测试 fuzzy_replace 的四级匹配策略。"""

    def test_l1_exact_unique_match(self) -> None:
        original = "hello world\nfoo bar\nhello world"
        result = fuzzy_replace(original, "foo bar", "replaced")
        assert result == "hello world\nreplaced\nhello world"

    def test_l1_exact_multiple_matches_raises(self) -> None:
        original = "hello\nhello"
        with pytest.raises(ValueError, match="匹配到了 2 处"):
            fuzzy_replace(original, "hello", "hi")

    def test_l1_exact_no_match_falls_through(self) -> None:
        original = "hello world"
        with pytest.raises(ValueError, match="找不到该代码片段"):
            fuzzy_replace(original, "nonexistent", "replacement")

    def test_l2_newline_normalization(self) -> None:
        original = "line1\r\nline2\r\nline3"
        old = "line1\nline2"
        result = fuzzy_replace(original, old, "REPLACED")
        assert result == "REPLACED\nline3"

    def test_l2_crlf_in_old_text(self) -> None:
        original = "line1\nline2\nline3"
        old = "line1\r\nline2"
        result = fuzzy_replace(original, old, "REPLACED")
        assert result == "REPLACED\nline3"

    def test_l3_trim_space_match(self) -> None:
        original = "  hello world  \nfoo"
        old = "hello world"
        result = fuzzy_replace(original, old, "replaced")
        assert result == "  replaced  \nfoo"

    def test_l4_line_by_line_deindent(self) -> None:
        original = "    def foo():\n        pass\n    def bar():\n        pass"
        old = "def foo():\n    pass"
        result = fuzzy_replace(original, old, "def baz():\n    return 42")
        assert "def baz()" in result
        assert "def bar()" in result

    def test_replace_with_empty_new_text(self) -> None:
        original = "keep this\nremove this\nkeep that"
        result = fuzzy_replace(original, "remove this", "")
        assert result == "keep this\n\nkeep that"


class TestLineByLineReplace:
    """测试逐行去缩进匹配。"""

    def test_single_line_match(self) -> None:
        content = "line1\nline2\nline3"
        result = line_by_line_replace(content, "line2", "REPLACED")
        assert result == "line1\nREPLACED\nline3"

    def test_multiline_match_with_indentation(self) -> None:
        content = "    def foo():\n        pass\n    def bar():\n        pass"
        old = "def foo():\n    pass"
        result = line_by_line_replace(content, old, "def baz():\n    return 1")
        assert "def baz()" in result
        assert "def bar()" in result

    def test_no_match_raises(self) -> None:
        with pytest.raises(ValueError, match="找不到该代码片段"):
            line_by_line_replace("line1\nline2", "nonexistent", "x")

    def test_multiple_deindent_matches_raises(self) -> None:
        content = "    pass\n    pass"
        with pytest.raises(ValueError, match="匹配到了 2 处"):
            line_by_line_replace(content, "pass", "continue")

    def test_empty_old_lines_raises(self) -> None:
        with pytest.raises(ValueError, match="找不到该代码片段"):
            line_by_line_replace("content", "", "x")
