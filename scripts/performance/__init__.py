"""绩效报告模块注册表。

MODULES 顺序即报告顺序；charts 不是报告章节，单独经 build_charts() 后处理。
"""
from __future__ import annotations

from .returns import run_returns
from .risk import run_risk
from .trades import run_trades
from .positions import run_positions
from .charts import build_charts, Chart

MODULES = [
    ("returns", run_returns),
    ("risk", run_risk),
    ("trades", run_trades),
    ("positions", run_positions),
]

__all__ = ["MODULES", "build_charts", "Chart", "run_returns", "run_risk", "run_trades", "run_positions"]
