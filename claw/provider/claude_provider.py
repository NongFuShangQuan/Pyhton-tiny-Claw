"""provider.claude_provider: 适配 Anthropic Claude 协议 (可对接智谱 Anthropic 兼容端点)。

"""
from __future__ import annotations

import os
from typing import Any, Optional

from ..schema import (
    Message,
    RoleSystem,
    RoleUser,
    RoleAssistant,
    ToolCall,
    ToolDefinition,
    Usage,
)
from .interface import LLMProvider


class ClaudeProvider(LLMProvider):
    """基于官方 anthropic-python SDK 的 Provider 实现。"""

    def __init__(self, client: Any, model: str):
        self._client = client
        self._model = model

    def generate(
        self,
        messages: list[Message],
        available_tools: Optional[list[ToolDefinition]] = None,
    ) -> Message:
        anthropic_msgs: list[dict[str, Any]] = []
        system_prompt = ""

        for msg in messages:
            if msg.role == RoleSystem:
                system_prompt = msg.content

            elif msg.role == RoleUser:
                if msg.tool_call_id:
                    # 工具结果消息 - 智谱 Anthropic 兼容端点的 tool_result 块
                    anthropic_msgs.append(
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": msg.tool_call_id,
                                    "content": msg.content,
                                    "is_error": False,
                                }
                            ],
                        }
                    )
                else:
                    anthropic_msgs.append(
                        {"role": "user", "content": [{"type": "text", "text": msg.content}]}
                    )

            elif msg.role == RoleAssistant:
                blocks: list[dict[str, Any]] = []
                # 即使 Content 为空，也要填充一个空的 TextBlock，否则引发 1214 错误
                blocks.append({"type": "text", "text": msg.content})
                for tc in msg.tool_calls:
                    input_val = tc.arguments_as_value()
                    blocks.append(
                        {
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.name,
                            "input": input_val if isinstance(input_val, dict) else {},
                        }
                    )
                if blocks:
                    anthropic_msgs.append({"role": "assistant", "content": blocks})

        anthropic_tools: list[dict[str, Any]] = []
        for td in available_tools or []:
            schema = td.input_schema or {}
            props = schema.get("properties", {}) if isinstance(schema, dict) else {}
            reqs = schema.get("required", []) if isinstance(schema, dict) else []
            anthropic_tools.append(
                {
                    "name": td.name,
                    "description": td.description,
                    "input_schema": {
                        "type": "object",
                        "properties": props,
                        "required": reqs,
                    },
                }
            )

        params: dict[str, Any] = {
            "model": self._model,
            "max_tokens": 4096,
            "messages": anthropic_msgs,
        }
        if system_prompt:
            params["system"] = system_prompt
        if anthropic_tools:
            params["tools"] = anthropic_tools

        try:
            resp = self._client.messages.create(**params)
        except Exception as err:
            raise RuntimeError(f"Claude/Zhipu API 请求失败: {err}") from err

        result = Message(role=RoleAssistant, content="")

        # 提取 Token 消耗
        usage_obj = getattr(resp, "usage", None)
        if usage_obj is not None:
            input_t = int(getattr(usage_obj, "input_tokens", 0) or 0)
            output_t = int(getattr(usage_obj, "output_tokens", 0) or 0)
            if input_t > 0 or output_t > 0:
                result.usage = Usage(
                    prompt_tokens=input_t,
                    completion_tokens=output_t,
                )

        for block in resp.content:
            btype = getattr(block, "type", None)
            if btype == "text":
                result.content += block.text or ""
            elif btype == "tool_use":
                input_val = getattr(block, "input", {})
                import json as _json

                args_bytes = _json.dumps(input_val, ensure_ascii=False).encode("utf-8")
                result.tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=args_bytes,
                    )
                )

        return result


def NewZhipuClaudeProvider(model: str) -> ClaudeProvider:
    """构造直连智谱 Claude 兼容端点的 Provider。"""
    api_key = os.getenv("ZHIPU_API_KEY")
    if not api_key:
        raise RuntimeError("请设置 ZHIPU_API_KEY 环境变量")

    base_url = "https://open.bigmodel.cn/api/anthropic"

    from anthropic import Anthropic  # type: ignore

    client = Anthropic(api_key=api_key, base_url=base_url)
    return ClaudeProvider(client, model)


__all__ = ["ClaudeProvider", "NewZhipuClaudeProvider"]