"""风险模块：最大回撤、年化波动、Sharpe、Sortino、Calmar、滚动 Sharpe、最优/最差日。

样本 < min_sample_days 时降级（日报/周报样本天然不足，设计如此）。
口径见 references/report-metrics.md。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .base import PerfResult


def run_risk(ctx) -> PerfResult:
    res = PerfResult("risk")
    if ctx.nav is None or len(ctx.nav) < 2:
        res.degraded = True
        res.note = "无净值数据，无法计算风险指标"
        return res

    nav = ctx.nav.astype(float).dropna()
    rets = nav.pct_change().dropna()
    if len(rets) < ctx.min_sample_days:
        res.degraded = True
        res.note = f"样本不足 {len(rets)} 日（下限 {ctx.min_sample_days}），风险指标不可靠"
        res.data.update({"n_days": int(len(rets))})
        return res

    # 波动与收益
    std = float(rets.std(ddof=1))
    annualized_vol = std * np.sqrt(ctx.annualization)
    rf_daily = ctx.risk_free_rate / ctx.annualization
    mean_daily = float(rets.mean())
    sharpe = (mean_daily - rf_daily) / std * np.sqrt(ctx.annualization) if std > 0 else None
    downside = rets[rets < 0]
    dstd = float(downside.std(ddof=1)) if len(downside) > 1 else 0.0
    sortino = (mean_daily - rf_daily) / dstd * np.sqrt(ctx.annualization) if dstd > 0 else None

    # 年化收益（与 returns 模块同口径，供 Calmar）
    n_days = max(int((nav.index[-1] - nav.index[0]).days), 1)
    cumulative_return = float(nav.iloc[-1] / nav.iloc[0] - 1)
    annualized_return = (
        float((1 + cumulative_return) ** (ctx.annualization / n_days) - 1)
        if (1 + cumulative_return) > 0
        else None
    )

    # 最大回撤（含起止/修复日）
    roll_max = nav.cummax()
    drawdown = nav / roll_max - 1.0
    mdd = float(drawdown.min())
    mdd_end = drawdown.idxmin()
    peak_at_trough = float(roll_max[mdd_end])
    peak_series = nav[nav == peak_at_trough]
    mdd_start = peak_series.index[0] if len(peak_series) else nav.index[0]
    after = nav[nav.index > mdd_end]
    rec = after[after >= peak_at_trough]
    mdd_recovery = rec.index[0] if len(rec) else None

    calmar = (annualized_return / abs(mdd)) if (mdd < 0 and annualized_return is not None) else None

    # 滚动 Sharpe
    rolling = rets.rolling(ctx.rolling_sharpe_window).apply(
        lambda x: (x.mean() - rf_daily) / x.std(ddof=1) * np.sqrt(ctx.annualization)
        if x.std(ddof=1) > 0
        else np.nan,
        raw=True,
    )

    res.series["drawdown"] = drawdown
    res.series["rolling_sharpe"] = rolling
    res.data.update(
        {
            "mdd": mdd,
            "mdd_start": str(mdd_start.date()),
            "mdd_end": str(mdd_end.date()),
            "mdd_recovery": str(mdd_recovery.date()) if mdd_recovery is not None else None,
            "annualized_vol": annualized_vol,
            "sharpe": sharpe,
            "sortino": sortino,
            "calmar": calmar,
            "rolling_sharpe_latest": float(rolling.iloc[-1]) if not pd.isna(rolling.iloc[-1]) else None,
            "best_day": {"date": str(rets.idxmax().date()), "ret": float(rets.max())},
            "worst_day": {"date": str(rets.idxmin().date()), "ret": float(rets.min())},
            "n_days": int(len(rets)),
        }
    )
    return res
