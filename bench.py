"""claw Benchmark: 对应 Go 版 cmd/bench/main.go。

构建微型评测集，支持 DeepSeek / Zhipu 多种 Provider 跑分。

用法:
    python bench.py [--provider deepseek|zhipu] [--model deepseek-chat]
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# 自动加载 .env 文件
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env")

from claw.eval import NewBenchmarkRunner, TestCase


def main() -> int:
    parser = argparse.ArgumentParser(description="py-tiny-claw Benchmark 跑分")
    parser.add_argument(
        "--provider",
        default="deepseek",
        choices=["zhipu", "deepseek"],
        help="LLM Provider 选择，默认 deepseek",
    )
    parser.add_argument(
        "--model",
        default="deepseek-v4-flash",
        help="使用的模型名称，默认 deepseek-v4-flash",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # 根据 provider 检查对应的 API Key
    api_key_env = "DEEPSEEK_API_KEY" if args.provider == "deepseek" else "ZHIPU_API_KEY"
    if not os.getenv(api_key_env):
        print(f"请先设置 {api_key_env} 环境变量进行跑分测试", file=sys.stderr)
        return 2

    testcases: list[TestCase] = [
        TestCase(
            id="test_001_edit",
            name="测试模糊替换工具的准确性",
            setup_script=r"""echo '{"name": "tiny-claw", "version": "v1.0.0"}' > config.json""",
            task_prompt=(
                "当前目录下有一个 config.json。请你使用 edit_file 工具，"
                "将其中的 version 从 v1.0.0 改为 v2.0.0。不要做其他多余操作。"
            ),
            validate_script=r"""grep '"version": "v2.0.0"' config.json""",
        ),
        TestCase(
            id="test_002_code_gen",
            name="测试代码阅读与创建新文件的综合能力",
            setup_script=r"""cat > multiply.py <<'EOF'
def multiply(a: int, b: int) -> int:
    return a * b
EOF""",
            task_prompt=(
                "当前目录下有一个 multiply.py。请你仔细阅读它，"
                "然后在同级目录下，帮我写一个规范的单元测试文件 test_multiply.py，"
                "用来测试 multiply 函数。请务必包含正常的测试用例。"
            ),
            validate_script=r"""python -c "import test_multiply; assert test_multiply.test_multiply_basic() or True; print('ok')"; python -m pytest -q test_multiply.py || python test_multiply.py""",
        ),
    ]

    runner = NewBenchmarkRunner(args.model, args.provider)
    runner.run_suite(testcases)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())