"""observability.tracker: 装饰式 Provider，追踪单次 API 调用的成本与延迟。

"""
from __future__ import annotations

import logging
import time
from typing import Optional

from ..context.session import Session
from ..schema import Message, ToolDefinition
from ..provider.interface import LLMProvider


_logger = logging.getLogger("claw.tracker")


# 模型定价参考 (元 / 百万 tokens)
# 注：如实际价格有变动，请在此处更新
PricingModel: dict[str, dict[str, float]] = {
    # 智谱 GLM 系列
    "glm-4.5-air": {"input_price": 0.15, "output_price": 0.15},
    # DeepSeek 系列 (官方定价，人民币)
    "deepseek-chat": {"input_price": 1.0, "output_price": 2.0},
    "deepseek-reasoner": {"input_price": 4.0, "output_price": 16.0},
    "deepseek-v4-flash": {"input_price": 1.0, "output_price": 2.0},
}


class CostTracker(LLMProvider):
    """装饰器：包裹真实 Provider，统计每次调用的 token 与花费。"""

    def __init__(
        self,
        next_provider: LLMProvider,
        model_name: str,
        session: Optional[Session] = None,
    ):
        self._next = next_provider
        self._model_name = model_name
        self._session = session

    def generate(
        self,
        messages: list[Message],
        available_tools: Optional[list[ToolDefinition]] = None,
    ) -> Message:
        start = time.time()
        try:
            resp = self._next.generate(messages, available_tools)
        except Exception:
            latency = time.time() - start
            _logger.error("[Tracker] ❌ API 调用失败，耗时: %.2fs", latency)
            raise

        latency = time.time() - start

        if resp.usage is not None:
            prompt_tokens = resp.usage.prompt_tokens
            completion_tokens = resp.usage.completion_tokens

            cost = 0.0
            price = PricingModel.get(self._model_name)
            if price is not None:
                cost = (
                    prompt_tokens * price["input_price"]
                    + completion_tokens * price["output_price"]
                ) / 1_000_000

            _logger.info(
                "[Tracker] 📊 API 调用完成 | 耗时: %.2fs | 输入: %d tk | 输出: %d tk | 花费: ¥%.6f",
                latency,
                prompt_tokens,
                completion_tokens,
                cost,
            )

            if self._session is not None:
                self._session.record_usage(prompt_tokens, completion_tokens, cost)
                _logger.info(
                    "[Tracker] 💰 当前会话 (%s) 累计花费: ¥%.6f",
                    self._session.id,
                    self._session.total_cost_cny,
                )
        else:
            _logger.warning(
                "[Tracker] ⚠️ API 调用完成，但未返回 Usage 数据 | 耗时: %.2fs", latency
            )

        return resp


def NewCostTracker(
    next_provider: LLMProvider,
    model_name: str,
    session: Optional[Session] = None,
) -> CostTracker:
    return CostTracker(next_provider, model_name, session)


__all__ = ["CostTracker", "NewCostTracker", "PricingModel"]