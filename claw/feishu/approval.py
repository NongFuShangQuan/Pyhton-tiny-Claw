"""feishu.approval: 飞书人工审批管理器与危险命令特征库。

"""
from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass
from typing import Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .bot import FeishuReporter


_logger = logging.getLogger("claw.feishu.approval")


@dataclass
class ApprovalResult:
    allowed: bool
    reason: str = ""


# 通知器签名: (notice_text) -> None，可由飞书 Reporter 或终端打印实现
NoticeSender = Callable[[str], None]


class ApprovalManager:
    def __init__(self) -> None:
        self._mu = threading.RLock()
        self._pending: dict[str, threading.Event] = {}
        self._results: dict[str, ApprovalResult] = {}

    def wait_for_approval(
        self,
        task_id: str,
        tool_name: str,
        args: str,
        notice_sender: Optional[NoticeSender] = None,
    ) -> "tuple[bool, str]":
        """阻塞当前线程，等待人类通过 approve/reject 命令放行或拒绝。"""
        ev = threading.Event()

        with self._mu:
            self._pending[task_id] = ev

        notice_msg = (
            f"⚠️ **高危操作审批请求**\n"
            f"Agent 试图执行以下动作:\n"
            f"- 工具: {tool_name}\n"
            f"- 参数: {args}\n\n"
            f"任务 ID: **{task_id}**\n\n"
            f'👉 请回复 "approve {task_id}" 或 "reject {task_id}" 决定是否放行。'
        )

        if notice_sender is not None:
            try:
                notice_sender(notice_msg)
            except Exception as e:  # noqa: BLE001
                _logger.error("[Approval] 通知发送失败: %s", e)
        else:
            print(f"\n\033[31m[需要审批 TaskID: {task_id}]\033[0m {notice_msg}\n")

        _logger.info("[Approval] 发送审批请求 (TaskID: %s)，线程挂起等待...", task_id)

        # 阻塞等待
        ev.wait()

        with self._mu:
            result = self._results.pop(task_id, ApprovalResult(False, "未知"))
            self._pending.pop(task_id, None)

        return result.allowed, result.reason

    def resolve_approval(
        self,
        task_id: str,
        allowed: bool,
        reason: str,
    ) -> None:
        """由飞书 Bot 收到 approve/reject 指令时调用，唤醒挂起的线程。"""
        with self._mu:
            ev = self._pending.get(task_id)
            if ev is not None:
                self._results[task_id] = ApprovalResult(allowed, reason)

        if ev is not None:
            _logger.info(
                "[Approval] 收到飞书审批结果 (TaskID: %s, Allowed: %s)",
                task_id,
                allowed,
            )
            ev.set()


GlobalApprovalMgr = ApprovalManager()


# 危险命名黑名单
_DANGEROUS_PATTERNS = [
    r"rm\s+-r",      # 级联删除
    r"sudo\s+",      # 提权
    r"drop\s+",      # 危险 DB 命令
    r">.*\.go",      # 覆写源码 (与原项目对齐)
    r"nginx\s+-s",   # 拦截 Nginx 服务重启/停止
    r"systemctl\s+",  # 系统级服务
    r"kill\s+",      # 杀进程
]
_DANGEROUS_REGEXES = [re.compile(p) for p in _DANGEROUS_PATTERNS]


def IsDangerousCommand(tool_name: str, args: str) -> bool:
    """白名单放行 read_file；对 write/file 与 bash 命中黑名单时返回 True。"""
    if tool_name == "read_file":
        return False

    if tool_name in ("write_file", "edit_file"):
        return True

    if tool_name == "bash":
        for rx in _DANGEROUS_REGEXES:
            if rx.search(args):
                return True
    return False


__all__ = [
    "ApprovalResult",
    "ApprovalManager",
    "GlobalApprovalMgr",
    "IsDangerousCommand",
    "NoticeSender",
]