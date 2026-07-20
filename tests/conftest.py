"""pytest 共享配置与 fixtures。"""
from __future__ import annotations

import sys
from pathlib import Path

# 将项目根目录加入 sys.path，便于直接 `pytest tests/` 运行
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
