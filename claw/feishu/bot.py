"""feishu.bot: 飞书 Webhook Bot + 飞书 Reporter 实现。


由于 Python 生态中，飞书官方 SDK 在不同版本接口差异较大，本模块采用
"requests 直接调用飞书 OpenAPI" 的极简方案，依赖 `requests` 与 `flask`，
不引入额外 SDK 依赖，便于跨平台部署与排错。
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

import requests

from ..context import GlobalSessionMgr, Session
from ..engine import AgentEngine, Reporter
from ..schema import Message, RoleUser
from .approval import GlobalApprovalMgr, IsDangerousCommand


_logger = logging.getLogger("claw.feishu.bot")


# ==========================================================
# 1. Context 传递机制
# ==========================================================


class ReporterContextAdapter:
    """Python 没有 context.Context, 我们用本地线程存储来传递 Reporter。"""

    def __init__(self) -> None:
        self._local = threading.local()

    def with_reporter(self, reporter: Reporter) -> "ReporterContextAdapter":
        # 在同一线程内通过副本传递（线程间不会互相污染）
        self._local.reporter = reporter
        return self

    def reporter(self) -> Optional[Reporter]:
        return getattr(self._local, "reporter", None)


# 全局绑定点 (类似 Go 的 reporterKey{})
ReporterContext = ReporterContextAdapter()


def ContextWithReporter(reporter: Reporter) -> ReporterContextAdapter:
    return ReporterContext.with_reporter(reporter)


def ReporterFromContext() -> Optional[Reporter]:
    return ReporterContext.reporter()


# ==========================================================
# 2. 飞书 Bot 调度器
# ==========================================================

AgentEngineFactory = Callable[[Session], AgentEngine]


@dataclass
class _FeishuCreds:
    app_id: str
    app_secret: str


def _load_creds() -> _FeishuCreds:
    app_id = os.getenv("FEISHU_APP_ID", "")
    app_secret = os.getenv("FEISHU_APP_SECRET", "")
    if not app_id or not app_secret:
        raise RuntimeError("请设置 FEISHU_APP_ID 和 FEISHU_APP_SECRET")
    return _FeishuCreds(app_id, app_secret)


class FeishuBot:
    """飞书 Bot 调度中心。

    使用飞书 OpenAPI (im/v1/messages) 发送文本消息。
    """

    def __init__(
        self,
        factory: AgentEngineFactory,
        work_dir: str,
        app_id: Optional[str] = None,
        app_secret: Optional[str] = None,
    ) -> None:
        self.factory = factory
        self.work_dir = work_dir

        creds = _load_creds() if (app_id is None or app_secret is None) else _FeishuCreds(
            app_id, app_secret
        )
        self.app_id = creds.app_id
        self.app_secret = creds.app_secret
        self._access_token: str = ""
        self._token_lock = threading.Lock()
        self._token_expires_at = 0.0

    # ---- Open token --------------------------------------------

    def _get_access_token(self) -> str:
        with self._token_lock:
            now = time.time()
            if self._access_token and now < self._token_expires_at - 30:
                return self._access_token
            url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
            payload = {"app_id": self.app_id, "app_secret": self.app_secret}
            try:
                resp = requests.post(url, json=payload, timeout=10)
                resp.raise_for_status()
                data = resp.json()
                token = data["tenant_access_token"]
                expire = int(data.get("expire", 7200))
                self._access_token = token
                self._token_expires_at = now + expire
                return token
            except Exception as e:  # noqa: BLE001
                _logger.exception("[Feishu] 获取 tenant_access_token 失败: %s", e)
                raise

    # ---- Sending messages --------------------------------------

    def send_msg(self, chat_id: str, text: str) -> None:
        try:
            token = self._get_access_token()
            url = "https://open.feishu.cn/open-apis/im/v1/messages"
            params = {"receive_id_type": "chat_id"}
            body = {
                "receive_id": chat_id,
                "msg_type": "text",
                "content": json.dumps({"text": text}),
            }
            requests.post(
                url,
                params=params,
                json=body,
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
        except Exception as e:  # noqa: BLE001
            _logger.exception("[Feishu] 发送消息失败: %s", e)

    # ---- Event handling ----------------------------------------

    def handle_event(self, body: dict) -> dict:
        """处理从 Webhook / 长连接接收到的飞书事件 payload。"""
        # 飞书 IM v1 事件格式
        event = body.get("event", {})
        msg = event.get("message") or {}
        content_raw = msg.get("content", "")
        chat_id = msg.get("chat_id", "")

        try:
            content_obj = json.loads(content_raw)
            content_str = content_obj.get("text", "") if isinstance(content_obj, dict) else ""
        except json.JSONDecodeError:
            # 退化处理：尝试剥离 {"text":"..."}
            m = re.match(r'^\{"text":"(.+)"\}$', content_raw or "")
            content_str = m.group(1) if m else content_raw

        _logger.info("[Feishu] 收到会话 %s 消息: %s", chat_id, content_str)

        # 拦截审批口令
        if content_str.startswith("approve "):
            task_id = content_str[len("approve ") :].strip()
            GlobalApprovalMgr.resolve_approval(task_id, True, "人类管理员已批准操作")
            _logger.info("[Feishu] 会话 %s: ✅ 已为您批准任务 %s", chat_id, task_id)
            return {"status": "ok"}
        if content_str.startswith("reject "):
            task_id = content_str[len("reject ") :].strip()
            GlobalApprovalMgr.resolve_approval(
                task_id,
                False,
                "人类管理员认为该操作存在极高风险，已无情拒绝",
            )
            _logger.info("[Feishu] 会话 %s: 🚫 已拒绝任务 %s", chat_id, task_id)
            return {"status": "ok"}

        # 普通对话拉起 Agent
        threading.Thread(
            target=self._handle_agent_run,
            args=(chat_id, content_str),
            daemon=True,
        ).start()
        return {"status": "accepted"}

    def _handle_agent_run(self, chat_id: str, prompt: str) -> None:
        reporter = FeishuReporter(self, chat_id)
        sess = GlobalSessionMgr.get_or_create(chat_id, self.work_dir)
        sess.append(Message(role=RoleUser, content=prompt))
        eng = self.factory(sess)

        # 设置本线程 Reporter 绑定，供中间件取回
        ContextWithReporter(reporter)

        err = eng.run(sess, reporter)
        if err is not None:
            reporter.on_message(f"❌ Agent 运行崩溃: {err}")


# ==========================================================
# 3. 飞书 Reporter 实现
# ==========================================================


class FeishuReporter(Reporter):
    def __init__(self, bot: FeishuBot, chat_id: str) -> None:
        self._bot = bot
        self._chat_id = chat_id

    def send_msg(self, text: str) -> None:
        self._bot.send_msg(self._chat_id, text)

    def on_thinking(self, ctx: Optional[Any] = None) -> None:
        self.send_msg("🤔 模型正在慢思考 (Thinking)...")

    def on_tool_call(
        self,
        tool_name: str,
        args: str,
        ctx: Optional[Any] = None,
    ) -> None:
        self.send_msg(f"🛠️ **正在执行工具**：`{tool_name}`\n参数：`{args}`")

    def on_tool_result(
        self,
        tool_name: str,
        result: str,
        is_error: bool,
        ctx: Optional[Any] = None,
    ) -> None:
        if is_error:
            self.send_msg(f"⚠️ **执行报错** ({tool_name})：\n{result}")
        else:
            self.send_msg(f"✅ **执行成功** ({tool_name})")

    def on_message(self, content: str, ctx: Optional[Any] = None) -> None:
        self.send_msg(content)


def NewFeishuBotWithFactory(factory: AgentEngineFactory, work_dir: str) -> FeishuBot:
    return FeishuBot(factory, work_dir)


__all__ = [
    "FeishuBot",
    "NewFeishuBotWithFactory",
    "FeishuReporter",
    "AgentEngineFactory",
    "ReporterContextAdapter",
    "ContextWithReporter",
    "ReporterFromContext",
]