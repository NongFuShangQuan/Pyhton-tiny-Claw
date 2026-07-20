"""engine.reminder: 死循环探测与提醒注入。

"""
from __future__ import annotations

import hashlib
import logging
from typing import Optional

from ..schema import Message, RoleUser, ToolCall, ToolResult


_logger = logging.getLogger("claw.reminder")


class ReminderInjector:
    def __init__(self) -> None:
        self._consecutive_failures: dict[str, int] = {}

    def check_and_inject(
        self,
        last_tool_call: Optional[ToolCall],
        last_result: Optional[ToolResult],
    ) -> Optional[Message]:
        if last_tool_call is None or last_result is None:
            return None

        fingerprint = _generate_fingerprint(last_tool_call.name, last_tool_call.arguments_to_str())

        if not last_result.is_error:
            self._consecutive_failures.clear()
            return None

        self._consecutive_failures[fingerprint] = (
            self._consecutive_failures.get(fingerprint, 0) + 1
        )
        fail_count = self._consecutive_failures[fingerprint]

        _logger.info(
            "[Reminder] 监控到工具 %s 执行失败，该参数特征连续失败次数: %d",
            last_tool_call.name,
            fail_count,
        )

        if fail_count >= 3:
            _logger.warning("[Reminder] ⚠️ 触发死循环干预！注入强力修正指令。")

            nudge_msg = (
                "[SYSTEM REMINDER 警告]\n"
                f"你似乎陷入了死循环。你刚刚连续 {fail_count} 次使用相同的参数调用了 "
                f"'{last_tool_call.name}' 工具，并且都失败了。\n"
                "请立即停止这种无效的重试！你的注意力被当前的报错过度吸引了。\n"
                "你需要：\n"
                "1. 停止猜测参数。跳出当前的局部思维。\n"
                "2. 彻底改变你的策略。\n"
                "3. 如果你确实无法通过系统工具解决当前问题，请直接结束任务并向用户说明你需要什么"
                "人工帮助，而不是继续盲目消耗 API 资源尝试。"
            )

            return Message(role=RoleUser, content=nudge_msg)

        return None


def NewReminderInjector() -> ReminderInjector:
    return ReminderInjector()


def _generate_fingerprint(tool_name: str, args_bytes: str) -> str:
    """生成工具调用特征指纹。"""
    h = hashlib.md5()
    h.update(tool_name.encode("utf-8"))
    h.update(args_bytes.encode("utf-8"))
    return h.hexdigest()


__all__ = ["ReminderInjector", "NewReminderInjector"]