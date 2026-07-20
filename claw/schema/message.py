"""schema.message: 大模型消息与工具协议的统一类型定义。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
import json


Role = str
RoleSystem: Role = "system"
RoleUser: Role = "user"
RoleAssistant: Role = "assistant"


@dataclass
class Usage:
    """单次大模型 API 调用的 Token 消耗统计。"""

    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass
class ToolCall:
    """模型侧的工具调用请求。"""

    id: str
    name: str
    arguments: Any  # json.RawMessage 等价物：保留原始 dict 或 str

    def to_dict(self) -> dict[str, Any]:
        """序列化为纯 dict，便于 JSON 化与跨调用传递。"""
        args = self.arguments
        if isinstance(args, (dict, list)):
            return {"id": self.id, "name": self.name, "arguments": args}
        if isinstance(args, str):
            try:
                return {"id": self.id, "name": self.name, "arguments": json.loads(args)}
            except json.JSONDecodeError:
                return {"id": self.id, "name": self.name, "arguments": args}
        return {"id": self.id, "name": self.name, "arguments": args}

    def arguments_as_value(self) -> Any:
        """以可直接 JSON 序列化的形式返回 arguments。"""
        if isinstance(self.arguments, (dict, list)):
            return self.arguments
        if isinstance(self.arguments, (bytes, bytearray)):
            try:
                return json.loads(self.arguments)
            except json.JSONDecodeError:
                return self.arguments.decode("utf-8", errors="replace")
        if isinstance(self.arguments, str):
            try:
                return json.loads(self.arguments)
            except json.JSONDecodeError:
                return self.arguments
        return self.arguments

    def arguments_to_json_bytes(self) -> bytes:
        """以 bytes 形式返回 arguments (与 Go 的 json.RawMessage 表现一致)。"""
        if isinstance(self.arguments, (bytes, bytearray)):
            return bytes(self.arguments)
        if isinstance(self.arguments, (dict, list)):
            return json.dumps(self.arguments, ensure_ascii=False).encode("utf-8")
        if isinstance(self.arguments, str):
            return self.arguments.encode("utf-8")
        return json.dumps(self.arguments, ensure_ascii=False).encode("utf-8")

    def arguments_to_str(self) -> str:
        """以字符串形式返回 arguments，供 OpenAI 兼容协议使用。"""
        if isinstance(self.arguments, str):
            return self.arguments
        if isinstance(self.arguments, (bytes, bytearray)):
            return bytes(self.arguments).decode("utf-8", errors="replace")
        if isinstance(self.arguments, (dict, list)):
            return json.dumps(self.arguments, ensure_ascii=False)
        return json.dumps(self.arguments, ensure_ascii=False)

    # Go 兼容别名
    arguments_to_str_or_raw = arguments_to_str


@dataclass
class Message:
    """统一消息结构。"""

    role: Role
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str = ""
    usage: Optional[Usage] = None

    def to_dict(self) -> dict[str, Any]:
        """转纯 dict，便于序列化或日志输出。"""
        d: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_calls:
            d["tool_calls"] = [tc.to_dict() for tc in self.tool_calls]
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        if self.usage is not None:
            d["usage"] = {
                "prompt_tokens": self.usage.prompt_tokens,
                "completion_tokens": self.usage.completion_tokens,
            }
        return d


@dataclass
class ToolResult:
    """工具执行结果。"""

    tool_call_id: str
    output: str
    is_error: bool = False


@dataclass
class ToolDefinition:
    """对外暴露的工具定义。"""

    name: str
    description: str
    input_schema: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }