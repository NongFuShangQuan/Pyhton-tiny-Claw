"""eval.benchmark: Harness Benchmark 自动评测器。

"""
from __future__ import annotations

import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from ..context import NewSession
from ..engine import NewAgentEngine
from ..factory import build_registry, create_provider
from ..observability import NewCostTracker
from ..schema import Message, RoleUser


_logger = logging.getLogger("claw.eval")


@dataclass
class TestCase:
    id: str
    name: str
    setup_script: str = ""
    task_prompt: str = ""
    validate_script: str = ""
    max_turns: int = 0  # 兼容字段，目前 Python 版未实现按 turn 截停


@dataclass
class TestResult:
    test_case_id: str
    passed: bool
    total_cost_cny: float = 0.0
    duration_ms: int = 0
    error_msg: str = ""


class BenchmarkRunner:
    def __init__(self, model_name: str, provider_name: str = "zhipu") -> None:
        self.model_name = model_name
        self.provider_name = provider_name

    def run_suite(self, testcases: list[TestCase]) -> None:
        _logger.info("==================================================")
        _logger.info(
            "🚀 启动自动化 Harness Benchmark 评估... | Provider: %s | 模型: %s",
            self.provider_name,
            self.model_name,
        )
        _logger.info("==================================================")

        results: list[TestResult] = []
        passed_count = 0
        total_cost = 0.0

        for tc in testcases:
            _logger.info("\n>>> ⏳ 正在执行用例 [%s]: %s", tc.id, tc.name)
            res = self._run_single(tc)
            results.append(res)
            if res.passed:
                passed_count += 1
                _logger.info(
                    ">>> ✅ 用例 [%s] 测试通过! | 耗时: %dms | 花费: $%.6f",
                    tc.id,
                    res.duration_ms,
                    res.total_cost_cny,
                )
            else:
                _logger.error(">>> ❌ 用例 [%s] 测试失败! | 错误: %s", tc.id, res.error_msg)
            total_cost += res.total_cost_cny

        _logger.info("\n================ 🏆 跑分终极报告 ================")
        denom = len(testcases) or 1
        _logger.info(
            "总用例数: %d | 成功数: %d | 成功率: %.2f%%",
            len(testcases),
            passed_count,
            passed_count * 100.0 / denom,
        )
        _logger.info("总消耗成本: $%.6f", total_cost)
        _logger.info("==================================================")

    def _run_single(self, tc: TestCase) -> TestResult:
        start = time.time()

        # 1. 为每个用例创建一个绝对干净的沙箱
        cwd = os.getcwd()
        work_dir = Path(cwd) / f"workspace/{tc.id}_{int(time.time())}"
        work_dir.mkdir(parents=True, exist_ok=True)

        # 2. (可选) Setup 准备靶机
        if tc.setup_script:
            try:
                subprocess.run(
                    ["bash", "-c", tc.setup_script],
                    cwd=str(work_dir),
                    check=True,
                    shell=False,
                    capture_output=True,
                )
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                return TestResult(
                    test_case_id=tc.id,
                    passed=False,
                    error_msg=f"靶机 Setup 失败: {e}",
                )

        # 3. 组装带 Tracker 的引擎
        try:
            real_provider = create_provider(self.provider_name, self.model_name)
        except Exception as e:  # noqa: BLE001
            return TestResult(
                test_case_id=tc.id,
                passed=False,
                error_msg=f"Provider 初始化失败: {e}",
            )

        session = NewSession(tc.id, str(work_dir))
        tracked = NewCostTracker(real_provider, self.model_name, session)
        registry = build_registry(work_dir)

        eng = NewAgentEngine(tracked, registry, False, False)

        # 4. 让 Agent 开始干活
        session.append(Message(role=RoleUser, content=tc.task_prompt))
        err = eng.run(session, None)
        if err is not None:
            return TestResult(
                test_case_id=tc.id,
                passed=False,
                error_msg=f"Agent 崩溃: {err}",
            )

        # 5. 校验脚本
        try:
            out = subprocess.run(
                ["bash", "-c", tc.validate_script],
                cwd=str(work_dir),
                capture_output=True,
                text=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            return TestResult(
                test_case_id=tc.id,
                passed=False,
                error_msg=f"验证脚本执行异常: {e}",
            )

        duration_ms = int((time.time() - start) * 1000)

        if out.returncode != 0:
            return TestResult(
                test_case_id=tc.id,
                passed=False,
                total_cost_cny=session.total_cost_cny,
                duration_ms=duration_ms,
                error_msg=f"验证脚本执行失败: {out.stdout}{out.stderr}",
            )

        return TestResult(
            test_case_id=tc.id,
            passed=True,
            total_cost_cny=session.total_cost_cny,
            duration_ms=duration_ms,
        )


def NewBenchmarkRunner(model: str, provider: str = "deepseek") -> BenchmarkRunner:
    return BenchmarkRunner(model, provider)


__all__ = [
    "TestCase",
    "TestResult",
    "BenchmarkRunner",
    "NewBenchmarkRunner",
]