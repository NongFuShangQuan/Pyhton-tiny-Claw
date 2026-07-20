"""context.compactor: 上下文压缩策略。
"""
from __future__ import annotations

import logging

from ..schema import Message, RoleSystem, RoleUser, RoleAssistant


_logger = logging.getLogger("claw.compactor")


class Compactor:
    """当上下文超过阈值时，折叠/截断早期消息，保留最近若干条原始工作记忆。"""

    def __init__(self, max_chars: int, retain_last_msgs: int):
        self.max_chars = max_chars
        self.retain_last_msgs = retain_last_msgs

    def compact(self, msgs: list[Message]) -> list[Message]:
        """对 msgs 执行压缩；不修改入参，返回新列表。"""
        current_length = self._estimate_length(msgs)

        if current_length < self.max_chars:
            return msgs

        _logger.warning(
            "[Compactor] ⚠️ 内存告警：当前上下文长度 (%d 字符) 超过阈值 (%d)，触发压缩清理...",
            current_length,
            self.max_chars,
        )

        compacted: list[Message] = []
        msg_count = len(msgs)
        protect_start = max(msg_count - self.retain_last_msgs, 0)

        for i, msg in enumerate(msgs):
            if msg.role == RoleSystem:
                compacted.append(msg)
                continue

            new_msg = Message(
                role=msg.role,
                content=msg.content,
                tool_calls=list(msg.tool_calls),
                tool_call_id=msg.tool_call_id,
                usage=msg.usage,
            )

            in_working_memory = i >= protect_start

            if msg.role == RoleUser and msg.tool_call_id:
                if not in_working_memory:
                    if len(msg.content) > 200:
                        new_msg.content = (
                            f"...[为了节省内存，早期的工具输出已被系统强制清理。原始长度: "
                            f"{len(msg.content)} 字节]..."
                        )
                else:
                    max_keep = 1000
                    if len(msg.content) > max_keep:
                        head = msg.content[:500]
                        tail = msg.content[len(msg.content) - 500 :]
                        new_msg.content = (
                            f"{head}\n\n...[内容过长，中间 {len(msg.content) - max_keep} "
                            f"字节已被系统截断]...\n\n{tail}"
                        )
            elif msg.role == RoleAssistant and msg.content:
                if not in_working_memory and len(msg.content) > 200:
                    new_msg.content = "...[早期的推理思考过程已折叠]..."

            compacted.append(new_msg)

        new_length = self._estimate_length(compacted)
        _logger.info(
            "[Compactor] ✅ 压缩完成。上下文长度从 %d 降至 %d 字符。",
            current_length,
            new_length,
        )
        return compacted

    @staticmethod
    def _estimate_length(msgs: list[Message]) -> int:
        length = 0
        for msg in msgs:
            length += len(msg.content)
            for tc in msg.tool_calls:
                length += len(tc.name if isinstance(tc.name, str) else str(tc.name))
                length += len(tc.arguments_to_str())
        return length


def NewCompactor(max_chars: int, retain_last_msgs: int) -> Compactor:
    return Compactor(max_chars, retain_last_msgs)


__all__ = ["Compactor", "NewCompactor"]