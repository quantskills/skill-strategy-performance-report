"""持仓与换手模块：当前持仓表、Top-N 集中度、单边换手、本期调仓次数。

口径见 references/report-metrics.md。
"""
from __future__ import annotations

import pandas as pd

from .base import PerfResult


def run_positions(ctx) -> PerfResult:
    res = PerfResult("positions")
    if ctx.positions is None or len(ctx.positions) == 0:
        res.degraded = True
        res.note = "缺少持仓数据，无法进行持仓/换手分析"
        return res

    pos = ctx.positions
    last_date = pos["date"].max()
    cur = pos[pos["date"] == last_date].copy()
    total_mv = float(cur["market_value"].sum())

    holdings = []
    if total_mv > 0:
        cur = cur.sort_values("market_value", ascending=False)
        for _, r in cur.iterrows():
            holdings.append(
                {
                    "symbol": str(r["symbol"]),
                    "market_value": float(r["market_value"]),
                    "weight": float(r["market_value"] / total_mv),
                }
            )

    top_n = min(ctx.top_n, len(holdings))
    top_concentration = float(sum(h["weight"] or 0 for h in holdings[:top_n])) if holdings else None

    # 单边换手：mean_t(Σ|w_t − w_{t-1}|) / 2（需要 ≥2 个日期）
    turnover = None
    if pos["date"].nunique() >= 2:
        dates = pd.DatetimeIndex(sorted(pos["date"].unique()))
        wdf = pos.pivot_table(index="date", columns="symbol", values="market_value", aggfunc="sum").reindex(dates).fillna(0.0)
        wdf = wdf.div(wdf.sum(axis=1), axis=0)
        diff = wdf.diff().abs().sum(axis=1)
        turnover = float(diff.iloc[1:].mean() / 2.0) if len(diff) > 1 else None

    # 本期调仓次数：窗口内成交日数（需成交数据）
    rebalance_count = None
    if ctx.trades is not None and len(ctx.trades) > 0:
        rebalance_count = int(ctx.trades["date"].nunique())

    res.data.update(
        {
            "as_of": str(pd.Timestamp(last_date).date()),
            "n_holdings": int(len(holdings)),
            "total_market_value": total_mv,
            "current_holdings": holdings,
            "top_n": int(top_n),
            "top_n_concentration": top_concentration,
            "one_way_turnover": turnover,
            "rebalance_count": rebalance_count,
        }
    )
    return res
