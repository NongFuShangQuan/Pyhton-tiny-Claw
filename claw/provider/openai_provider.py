"""provider.openai_provider: 适配 OpenAI 兼容协议 (默认对接智谱 GLM)。

对应 Go 版 internal/provider/openai.go。
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


class OpenAIProvider(LLMProvider):
    """基于官方 openai-python SDK 的 Provider 实现。"""

    def __init__(self, client: Any, model: str):
        self._client = client
        self._model = model

    def generate(
        self,
        messages: list[Message],
        available_tools: Optional[list[ToolDefinition]] = None,
    ) -> Message:
        openai_msgs: list[dict[str, Any]] = []

        for msg in messages:
            if msg.role == RoleSystem:
                openai_msgs.append({"role": "system", "content": msg.content})

            elif msg.role == RoleUser:
                if msg.tool_call_id:
                    # 工具结果消息
                    openai_msgs.append(
                        {
                            "role": "tool",
                            "tool_call_id": msg.tool_call_id,
                            "content": msg.content,
                        }
                    )
                else:
                    openai_msgs.append({"role": "user", "content": msg.content})

            elif msg.role == RoleAssistant:
                ast: dict[str, Any] = {
                    "role": "assistant",
                    # 即使 Content 为空，也要发给智谱，否则会触发 1214 错误码
                    "content": msg.content,
                }
                if msg.tool_calls:
                    ast["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": tc.arguments_to_str(),
                            },
                        }
                        for tc in msg.tool_calls
                    ]
                openai_msgs.append(ast)

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": openai_msgs,
        }

        if available_tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": td.name,
                        "description": td.description,
                        "parameters": td.input_schema,
                    },
                }
                for td in available_tools
            ]

        try:
            resp = self._client.chat.completions.create(**payload)
        except Exception as err:
            raise RuntimeError(f"OpenAI/Zhipu API 请求失败: {err}") from err

        choices = getattr(resp, "choices", None) or []
        if not choices:
            raise RuntimeError("API 返回了空的 Choices")

        choice = choices[0]
        choice_msg = choice.message

        result = Message(
            role=RoleAssistant,
            content=getattr(choice_msg, "content", "") or "",
        )

        # 提取 Usage 信息
        usage_obj = getattr(resp, "usage", None)
        if usage_obj is not None:
            prompt_tokens = int(getattr(usage_obj, "prompt_tokens", 0) or 0)
            completion_tokens = int(getattr(usage_obj, "completion_tokens", 0) or 0)
            if prompt_tokens > 0 or completion_tokens > 0:
                result.usage = Usage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                )

        tool_calls = getattr(choice_msg, "tool_calls", None) or []
        for tc in tool_calls:
            ttype = getattr(tc, "type", "function")
            if ttype != "function":
                continue
            func = tc.function
            result.tool_calls.append(
                ToolCall(
                    id=tc.id,
                    name=func.name,
                    arguments=func.arguments,
                )
            )

        return result


def NewZhipuOpenAIProvider(model: str) -> OpenAIProvider:
    """构造直连智谱 GLM (OpenAI 兼容协议) 的 Provider。"""
    api_key = os.getenv("ZHIPU_API_KEY")
    if not api_key:
        raise RuntimeError("请设置 ZHIPU_API_KEY 环境变量")

    base_url = "https://open.bigmodel.cn/api/paas/v4/"

    # 延迟导入，便于在没有安装 SDK 时也能 import 本模块做静态分析
    from openai import OpenAI  # type: ignore

    client = OpenAI(api_key=api_key, base_url=base_url)
    return OpenAIProvider(client, model)


def NewDeepSeekProvider(model: str = "deepseek-chat") -> OpenAIProvider:
    """构造直连 DeepSeek API (OpenAI 兼容协议) 的 Provider。

    Args:
        model: DeepSeek 模型名，可选 deepseek-chat (V3) 或 deepseek-reasoner (R1)。

    Requires:
        环境变量 DEEPSEEK_API_KEY。
    """
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("请设置 DEEPSEEK_API_KEY 环境变量")

    base_url = "https://api.deepseek.com"

    from openai import OpenAI  # type: ignore

    client = OpenAI(api_key=api_key, base_url=base_url)
    return OpenAIProvider(client, model)


__all__ = ["OpenAIProvider", "NewZhipuOpenAIProvider", "NewDeepSeekProvider"]