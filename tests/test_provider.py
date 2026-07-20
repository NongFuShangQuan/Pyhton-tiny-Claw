"""tests.test_provider: LLM Provider 工厂函数的单元测试。

测试 NewDeepSeekProvider / NewZhipuOpenAIProvider 的构造逻辑和参数验证。
"""
from __future__ import annotations

import os
from unittest.mock import patch, MagicMock

import pytest

from claw.provider.openai_provider import (
    NewZhipuOpenAIProvider,
    NewDeepSeekProvider,
    OpenAIProvider,
)


class TestNewDeepSeekProvider:
    def test_missing_api_key_raises(self) -> None:
        """未设置 DEEPSEEK_API_KEY 时应抛出 RuntimeError。"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
                NewDeepSeekProvider()

    def test_creates_provider_with_default_model(self) -> None:
        """设置 API Key 后应成功创建 OpenAIProvider，默认模型为 deepseek-chat。"""
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test-key"}, clear=True):
            with patch("claw.provider.openai_provider.OpenAI") as mock_openai:
                mock_client = MagicMock()
                mock_openai.return_value = mock_client

                provider = NewDeepSeekProvider()

                assert isinstance(provider, OpenAIProvider)
                assert provider._model == "deepseek-chat"
                # 验证 base_url 指向 DeepSeek
                mock_openai.assert_called_once_with(
                    api_key="sk-test-key",
                    base_url="https://api.deepseek.com",
                )

    def test_creates_provider_with_custom_model(self) -> None:
        """可以指定自定义模型名如 deepseek-reasoner。"""
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test-key"}, clear=True):
            with patch("claw.provider.openai_provider.OpenAI") as mock_openai:
                mock_client = MagicMock()
                mock_openai.return_value = mock_client

                provider = NewDeepSeekProvider("deepseek-reasoner")

                assert provider._model == "deepseek-reasoner"


class TestNewZhipuOpenAIProvider:
    def test_missing_api_key_raises(self) -> None:
        """未设置 ZHIPU_API_KEY 时应抛出 RuntimeError。"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(RuntimeError, match="ZHIPU_API_KEY"):
                NewZhipuOpenAIProvider("glm-4.5-air")

    def test_creates_provider_with_zhipu_base_url(self) -> None:
        """验证 base_url 指向智谱 API。"""
        with patch.dict(os.environ, {"ZHIPU_API_KEY": "sk-test-key"}, clear=True):
            with patch("claw.provider.openai_provider.OpenAI") as mock_openai:
                mock_client = MagicMock()
                mock_openai.return_value = mock_client

                provider = NewZhipuOpenAIProvider("glm-4.5-air")

                assert provider._model == "glm-4.5-air"
                mock_openai.assert_called_once_with(
                    api_key="sk-test-key",
                    base_url="https://open.bigmodel.cn/api/paas/v4/",
                )
