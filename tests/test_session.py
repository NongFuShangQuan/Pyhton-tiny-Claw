"""tests.test_session: Session 与会话管理器的单元测试。"""
from __future__ import annotations

import pytest

from claw.context.session import Session, SessionManager, NewSession, GlobalSessionMgr
from claw.schema import Message, RoleUser, RoleAssistant


class TestSession:
    def test_new_session(self) -> None:
        sess = NewSession("test_1", "/tmp/work")
        assert sess.id == "test_1"
        assert sess.work_dir == "/tmp/work"
        assert sess.total_prompt_tokens == 0
        assert sess.total_completion_tokens == 0
        assert sess.total_cost_cny == 0.0

    def test_append_single_message(self) -> None:
        sess = NewSession("s1", "/tmp")
        msg = Message(role=RoleUser, content="hello")
        sess.append(msg)
        mem = sess.get_working_memory(10)
        assert len(mem) == 1
        assert mem[0].content == "hello"

    def test_append_multiple_messages(self) -> None:
        sess = NewSession("s1", "/tmp")
        sess.append(
            Message(role=RoleUser, content="msg1"),
            Message(role=RoleAssistant, content="msg2"),
        )
        mem = sess.get_working_memory(10)
        assert len(mem) == 2

    def test_get_working_memory_with_limit(self) -> None:
        sess = NewSession("s1", "/tmp")
        for i in range(10):
            sess.append(Message(role=RoleUser, content=f"msg{i}"))
        mem = sess.get_working_memory(5)
        assert len(mem) == 5
        assert mem[0].content == "msg5"
        assert mem[-1].content == "msg9"

    def test_get_working_memory_below_limit(self) -> None:
        sess = NewSession("s1", "/tmp")
        sess.append(Message(role=RoleUser, content="only"))
        mem = sess.get_working_memory(10)
        assert len(mem) == 1

    def test_orphan_tool_result_removed(self) -> None:
        sess = NewSession("s1", "/tmp")
        # 第一条是孤立的 tool_result (没有对应的 assistant)
        sess.append(Message(role=RoleUser, content="orphan tool output", tool_call_id="call_1"))
        sess.append(Message(role=RoleUser, content="real question"))
        mem = sess.get_working_memory(2)
        # 孤立的 tool_result 应被移除
        assert len(mem) == 1
        assert mem[0].content == "real question"

    def test_valid_tool_result_kept(self) -> None:
        sess = NewSession("s1", "/tmp")
        sess.append(Message(role=RoleUser, content="question"))
        sess.append(Message(role=RoleUser, content="tool result", tool_call_id="call_1"))
        mem = sess.get_working_memory(2)
        # 第一条是普通 User 消息，不是 tool_result，不应被移除
        assert len(mem) == 2

    def test_record_usage(self) -> None:
        sess = NewSession("s1", "/tmp")
        sess.record_usage(100, 50, 0.001)
        assert sess.total_prompt_tokens == 100
        assert sess.total_completion_tokens == 50
        assert sess.total_cost_cny == 0.001

        sess.record_usage(200, 100, 0.002)
        assert sess.total_prompt_tokens == 300
        assert sess.total_cost_cny == 0.003

    def test_empty_append(self) -> None:
        sess = NewSession("s1", "/tmp")
        sess.append()  # 不传任何消息
        mem = sess.get_working_memory(10)
        assert len(mem) == 0


class TestSessionManager:
    def test_get_or_create_new(self) -> None:
        mgr = SessionManager()
        sess = mgr.get_or_create("new_session", "/tmp/work")
        assert sess.id == "new_session"
        assert sess.work_dir == "/tmp/work"

    def test_get_or_create_existing(self) -> None:
        mgr = SessionManager()
        s1 = mgr.get_or_create("same_id", "/tmp/a")
        s2 = mgr.get_or_create("same_id", "/tmp/b")
        assert s1 is s2  # 同一个对象
        assert s2.work_dir == "/tmp/a"  # 保留原来的 work_dir

    def test_different_sessions_isolated(self) -> None:
        mgr = SessionManager()
        s1 = mgr.get_or_create("id1", "/tmp/1")
        s2 = mgr.get_or_create("id2", "/tmp/2")
        s1.append(Message(role=RoleUser, content="for s1"))
        assert len(s2.get_working_memory(10)) == 0

    def test_global_session_mgr_is_singleton(self) -> None:
        assert GlobalSessionMgr is not None
        s = GlobalSessionMgr.get_or_create("global_test", "/tmp/g")
        assert s.id == "global_test"
