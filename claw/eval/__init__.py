"""eval 子包: 自动化基准评测 (Benchmark)。"""
from .benchmark import (
    TestCase,
    TestResult,
    BenchmarkRunner,
    NewBenchmarkRunner,
)

__all__ = [
    "TestCase",
    "TestResult",
    "BenchmarkRunner",
    "NewBenchmarkRunner",
]