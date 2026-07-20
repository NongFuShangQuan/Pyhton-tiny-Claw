"""context.session: 会话与全局会话管理器。

"""
from __future__ import annotations

import threading
import time
from typing import Optional

from ..schema import Message, RoleUser


class Session:
    """单个会话的主体记忆容器。"""

    def __init__(self, session_id: str, work_dir: str):
        self.id = session_id
        self.work_dir = work_dir
        self.created_at = time.time()
        self.updated_at = time.time()

        # 累计消耗的资源
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_cost_cny = 0.0

        self._history: list[Message] = []
        self._mu = threading.RLock()

    def append(self, *msgs: Message) -> None:
        """追加一条或多条消息。"""
        if not msgs:
            return
        with self._mu:
            self._history.extend(msgs)
            self.updated_at = time.time()

    def get_working_memory(self, limit: int) -> list[Message]:
        """获取最近 limit 条工作记忆。处理截断边缘的孤儿 tool_result。"""
        with self._mu:
            total = len(self._history)
            if total <= limit or limit <= 0:
                res = list(self._history)
            else:
                res = list(self._history[total - limit :])

        # 处理截断边缘的 ToolResult 孤儿问题
        while res:
            head = res[0]
            if head.role == RoleUser and head.tool_call_id:
                res = res[1:]
            else:
                break
        return res

    def record_usage(self, prompt: int, completion: int, cost: float) -> None:
        """外部 Tracker 调用，累加账单。"""
        with self._mu:
            self.total_prompt_tokens += prompt
            self.total_completion_tokens += completion
            self.total_cost_cny += cost


class SessionManager:
    """Session 的全局注册表 (多会话并发隔离)。"""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._mu = threading.RLock()

    def get_or_create(self, session_id: str, work_dir: str) -> Session:
        with self._mu:
            sess = self._sessions.get(session_id)
            if sess is not None:
                return sess
            sess = Session(session_id, work_dir)
            self._sessions[session_id] = sess
            return sess


# 进程级单例
GlobalSessionMgr = SessionManager()


def NewSession(session_id: str, work_dir: str) -> Session:
    """构造独立 Session (供 Benchmark / 子任务使用，不入注册表)。"""
    return Session(session_id, work_dir)


__all__ = ["Session", "SessionManager", "GlobalSessionMgr", "NewSession"]