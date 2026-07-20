"""claw AgentOps: 飞书侧的 ChatOps 服务端。对应 Go 版 cmd/agentops/main.go。

启动后:
    1. 监听 /webhook/event HTTP POST
    2. 解析飞书 IM 消息事件
    3. 拦截 approve/reject 人工审批口令
    4. 其他内容派给 Agent 引擎异步处理

需要环境变量:
    DEEPSEEK_API_KEY 或 ZHIPU_API_KEY
    FEISHU_APP_ID, FEISHU_APP_SECRET
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# 自动加载 .env 文件
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env")

from flask import Flask, request, jsonify

from claw.context import Session
from claw.engine import NewAgentEngine
from claw.factory import build_registry, create_provider
from claw.feishu import (
    IsDangerousCommand,
    NewFeishuBotWithFactory,
    GlobalApprovalMgr,
)
from claw.feishu.bot import ReporterContext
from claw.observability import NewCostTracker
from claw.schema import Message, ToolCall


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    provider_name = os.getenv("CLAW_PROVIDER", "deepseek")
    model_name = os.getenv("CLAW_MODEL", "deepseek-v4-flash")

    # 验证必要的 API Key
    api_key_env = "DEEPSEEK_API_KEY" if provider_name == "deepseek" else "ZHIPU_API_KEY"
    if not os.getenv(api_key_env) or not os.getenv("FEISHU_APP_ID"):
        print(f"❌ 请先设置 {api_key_env} 和飞书相关环境变量", file=sys.stderr)
        return 2

    work_dir = Path(os.getcwd()) / "workspace"
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        llm_provider = create_provider(provider_name, model_name)
        logging.info("🧠 AgentOps 启动 | Provider: %s | 模型: %s", provider_name, model_name)
    except Exception as e:
        print(f"❌ Provider 初始化失败: {e}", file=sys.stderr)
        return 2

    registry = build_registry(work_dir)

    # 安全拦截 Middleware
    def safety_middleware(call: ToolCall):
        args_str = call.arguments_to_str()
        if IsDangerousCommand(call.name, args_str):
            reporter = ReporterContext.reporter()
            notice_sender = (
                (lambda text: reporter.send_msg(text)) if reporter is not None else None
            )
            allowed, reason = GlobalApprovalMgr.wait_for_approval(
                call.id, call.name, args_str, notice_sender
            )
            if not allowed:
                return False, reason
            return True, ""
        return True, ""

    registry.use(safety_middleware)
    logging.info("🛡️ 安全防御 Middleware 已挂载。")

    def engine_factory(session: Session):
        tracked = NewCostTracker(llm_provider, model_name, session)
        return NewAgentEngine(tracked, registry, False, False)

    bot = NewFeishuBotWithFactory(engine_factory, str(work_dir))

    app = Flask("claw-agentops")

    @app.route("/webhook/event", methods=["POST"])
    def webhook():  # noqa: ANN202
        body = request.get_json(silent=True) or {}
        result = bot.handle_event(body)
        return jsonify(result)

    port = int(os.getenv("AGENTOPS_PORT", "48080"))
    logging.info("📡 Webhook 服务已启动，正在监听端口 %d...", port)
    try:
        app.run(host="0.0.0.0", port=port, debug=False)
    except KeyboardInterrupt:
        logging.info("收到中断信号，退出。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())