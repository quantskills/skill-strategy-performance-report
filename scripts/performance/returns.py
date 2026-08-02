"""收益模块：区间/累计/年化、分桶收益表、基准对比与超额曲线、对账。

口径见 references/report-metrics.md。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .base import PerfResult

# 频率 → 区间交易日数（semi_annual=126, annual=252）
FREQ_DAYS = {
    "daily": 1,
    "weekly": 5,
    "monthly": 21,
    "semi_annual": 126,
    "annual": 252,
}


def bucket_series(dates: pd.DatetimeIndex, frequency: str) -> pd.Series:
    """把日期序列映射到分桶标签（period_over_period 表用）。

    daily → 每日；weekly → ISO 周；monthly / semi_annual / annual → 自然月；custom → 每日。
    """
    if frequency in ("daily", "custom"):
        return pd.Series([d.strftime("%Y-%m-%d") for d in dates], index=dates)
    if frequency == "weekly":
        return pd.Series([d.strftime("%G-W%V") for d in dates], index=dates)
    return pd.Series([d.strftime("%Y-%m") for d in dates], index=dates)


def period_bounds(dates: pd.DatetimeIndex, frequency: str, custom_start=None, custom_end=None):
    """按频率取报告窗口 (start, end)。custom 缺起止返回 (None, None) → 调用方退化。"""
    if frequency == "custom":
        if custom_start and custom_end:
            return pd.Timestamp(custom_start), pd.Timestamp(custom_end)
        return None, None
    if len(dates) == 0:
        return None, None
    if frequency == "daily":
        return dates[-1], dates[-1]
    if frequency == "weekly":
        wk = dates[-1].strftime("%G-W%V")
        idx = dates[[d.strftime("%G-W%V") == wk for d in dates]]
        return idx[0], idx[-1]
    if frequency == "monthly":
        month = dates[-1].strftime("%Y-%m")
        idx = dates[[d.strftime("%Y-%m") == month for d in dates]]
        return idx[0], idx[-1]
    n = FREQ_DAYS.get(frequency)
    if n is None or len(dates) <= n:
        return dates[0], dates[-1]
    return dates[-n], dates[-1]


def run_returns(ctx) -> PerfResult:
    res = PerfResult("returns")
    if ctx.nav is None or len(ctx.nav) == 0:
        res.degraded = True
        res.note = "缺少净值或成交+持仓，无法生成收益"
        return res

    nav = ctx.nav.astype(float).dropna()
    rets = nav.pct_change().dropna()
    dates = nav.index

    s, e = period_bounds(dates, ctx.frequency, ctx.custom_start, ctx.custom_end)
    fallback = False
    if s is None or e is None:
        s, e = period_bounds(dates, "monthly", None, None)  # custom 缺起止 → 最近一个月
        fallback = True

    window = nav[(nav.index >= s) & (nav.index <= e)]
    if len(window) == 0:
        res.degraded = True
        res.note = f"区间 {s} ~ {e} 内无净值数据"
        return res

    wrets = rets[(rets.index > s) & (rets.index <= e)]  # 区间内日收益（不含窗口起点当日）
    period_return = float(window.iloc[-1] / window.iloc[0] - 1)
    cumulative_return = float(nav.iloc[-1] / nav.iloc[0] - 1)
    n_days = max(int((dates[-1] - dates[0]).days), 1)
    annualized_return = (
        float((1 + cumulative_return) ** (ctx.annualization / n_days) - 1)
        if (1 + cumulative_return) > 0
        else None
    )

    # 对账：prod(1+r_t) ≈ nav_end/nav_start（窗口 + 全序列）
    window_prod = float(np.prod(1 + wrets)) if len(wrets) else 1.0
    recon = abs(window_prod - (1 + period_return))
    cumulative_prod = float(np.prod(1 + rets)) if len(rets) else 1.0
    cumulative_residual = abs(cumulative_prod - (1 + cumulative_return))
    res.recon_residual = recon

    # 分桶收益表
    bdf = pd.DataFrame({"nav": nav.values, "bucket": bucket_series(dates, ctx.frequency).values}, index=dates)
    bucket_rets = []
    for b, g in bdf.groupby("bucket", sort=False):
        if len(g) >= 2:
            bucket_rets.append({"bucket": str(b), "ret": float(g["nav"].iloc[-1] / g["nav"].iloc[0] - 1)})

    # 基准对比（缺文件 → 省略子项，绝不编造指数收益）
    bench = None
    if ctx.benchmark_nav is not None and len(ctx.benchmark_nav) > 0 and ctx.benchmark_label != "无基准":
        bnav = ctx.benchmark_nav.astype(float).reindex(nav.index).ffill()
        bnav = bnav[~bnav.index.duplicated(keep="last")]
        bnav = bnav.div(bnav.iloc[0])
        nnorm = nav.div(nav.iloc[0])
        bwindow = bnav[(bnav.index >= s) & (bnav.index <= e)].dropna()
        if len(bwindow) >= 2:
            bench_period_return = float(bwindow.iloc[-1] / bwindow.iloc[0] - 1)
            bench = {
                "benchmark_label": ctx.benchmark_label,
                "bench_period_return": bench_period_return,
                "excess_arithmetic": period_return - bench_period_return,
                "excess_relative": float((1 + period_return) / (1 + bench_period_return) - 1),
            }
            res.series["bench_norm"] = bnav
            res.series["nav_norm"] = nnorm
        else:
            res.data["benchmark_note"] = "基准区间内数据不足，已省略基准子项"

    res.series["nav"] = nav
    res.data.update(
        {
            "nav_source": ctx.nav_source,
            "nav_note": ctx.nav_note,
            "period_start": str(s.date()) if s is not None else None,
            "period_end": str(e.date()) if e is not None else None,
            "period_return": period_return,
            "cumulative_return": cumulative_return,
            "annualized_return": annualized_return,
            "period_over_period": bucket_rets,
            "n_window_days": int(len(window)),
            "recon_residual": recon,
            "cumulative_residual": cumulative_residual,
            "benchmark": bench,
            "window_fallback": fallback,
        }
    )
    return res
