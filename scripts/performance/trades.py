"""交易模块：胜率、盈亏比、平均盈亏、PnL 分布（按桶/按标的）、持仓天数。

PnL 口径优先级：① 成交表 pnl 列 → ② FIFO 配平近似 → ③ 无法配平降级（绝不臆测）。
口径见 references/report-metrics.md。
"""
from __future__ import annotations

from collections import deque

import numpy as np
import pandas as pd

from .base import PerfResult, ensure_trade_cols
from .returns import bucket_series


def fifo_pnl(trades: pd.DataFrame) -> pd.Series | None:
    """FIFO 配平近似：对每个 symbol 按时间顺序买入/卖出配对，卖出以先进先出成本结算盈亏。

    某标的卖出数量超过已买入数量（无法配平）→ 整体返回 None（该口径不适用）。
    返回与 trades 行对齐的 PnL 序列（买入行为 0，卖出行为已实现盈亏）。
    """
    trades = ensure_trade_cols(trades)
    pnl = pd.Series(np.nan, index=trades.index, dtype=float)
    g = trades.sort_values("date")
    for _, group in g.groupby("symbol", sort=False):
        queue: deque[tuple[float, float]] = deque()  # (qty, unit_cost)
        for row in group.itertuples(index=True):
            qty = float(row.shares)
            price = float(row.price)
            if row.buy:
                queue.append((qty, price))
            elif row.sell:
                remaining = qty
                realized = 0.0
                while remaining > 1e-9 and queue:
                    q, cost = queue[0]
                    take = min(remaining, q)
                    realized += take * (price - cost)
                    remaining -= take
                    if take >= q - 1e-9:
                        queue.popleft()
                    else:
                        queue[0] = (q - take, cost)
                if remaining > 1e-9:
                    return None  # 卖超了 → 无法配平
                pnl.at[row.Index] = realized
    if pnl.isna().all():
        return None
    pnl = pnl.fillna(0.0)
    if "commission" in trades.columns:
        pnl = pnl - trades["commission"].fillna(0.0)
    return pnl


def run_trades(ctx) -> PerfResult:
    res = PerfResult("trades")
    if ctx.trades is None or len(ctx.trades) == 0:
        res.degraded = True
        res.note = "缺少成交数据，无法进行交易分析"
        return res

    trades = ctx.trades
    total_trades = int(len(trades))

    if "pnl" in trades.columns:
        pnl = trades["pnl"].fillna(0.0)
        pnl_source = "pnl_column"
    else:
        fifo = fifo_pnl(trades)
        if fifo is None:
            res.degraded = True
            res.note = "成交缺少 pnl 列且无法 FIFO 配平，无法计算交易 PnL"
            res.data.update({"pnl_source": "none", "total_trades": total_trades})
            return res
        pnl = fifo
        pnl_source = "fifo_mark_to_market"

    wins = pnl > 0
    losses = pnl < 0
    closed = int((pnl != 0).sum())
    gross_profit = float(pnl[wins].sum())
    gross_loss = float(-pnl[losses].sum())
    win_rate = float(wins.sum() / closed) if closed else None
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else None
    avg_win = float(pnl[wins].mean()) if wins.any() else None
    avg_loss = float(pnl[losses].mean()) if losses.any() else None

    # 按分桶 / 按标的 PnL
    trd_dates = pd.DatetimeIndex(sorted(trades["date"].unique()))
    buckets = bucket_series(trd_dates, ctx.frequency)
    bdf = pd.DataFrame({"pnl": pnl.values, "bucket": buckets.values})
    pnl_by_period = [{"bucket": str(b), "pnl": float(g["pnl"].sum())} for b, g in bdf.groupby("bucket", sort=False)]

    sdf = pd.DataFrame({"symbol": trades["symbol"].astype(str).values, "pnl": pnl.values})
    pnl_by_symbol = [
        {"symbol": str(sym), "pnl": float(g["pnl"].sum()), "n": int(len(g))}
        for sym, g in sdf.groupby("symbol", sort=False)
    ]

    # 持仓天数：FIFO 配对可得时（买→卖对）近似为卖方与对应买入日的营业日差
    holding_days = None
    if pnl_source == "fifo_mark_to_market":
        holding_days = _fifo_holding_days(trades)

    res.data.update(
        {
            "pnl_source": pnl_source,
            "total_trades": total_trades,
            "closed_trades": closed,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "pnl_by_period": pnl_by_period,
            "pnl_by_symbol": pnl_by_symbol,
            "pnl_list": [float(x) for x in pnl.tolist()],
            "holding_days": holding_days,
        }
    )
    if closed < 3:
        res.degraded = True
        res.note = f"平仓样本过少（{closed} 笔 < 3），胜率/盈亏比仅供参考"
    return res


def _fifo_holding_days(trades: pd.DataFrame) -> list[float] | None:
    """FIFO 配平下，估算每笔卖出的持仓天数（营业日，近似取自然日/7*5）。"""
    trades = ensure_trade_cols(trades)
    days: list[float] = []
    g = trades.sort_values("date")
    for _, group in g.groupby("symbol", sort=False):
        queue: deque[tuple[float, float, pd.Timestamp]] = deque()  # (qty, cost, buy_date)
        for row in group.itertuples(index=True):
            qty = float(row.shares)
            if row.buy:
                queue.append((qty, float(row.price), pd.Timestamp(row.date)))
            elif row.sell:
                remaining = qty
                while remaining > 1e-9 and queue:
                    q, _, buy_date = queue[0]
                    take = min(remaining, q)
                    n_cal = (pd.Timestamp(row.date) - buy_date).days
                    days.append(float(n_cal / 7.0 * 5.0))  # 营业日近似
                    remaining -= take
                    if take >= q - 1e-9:
                        queue.popleft()
                    else:
                        queue[0] = (q - take, queue[0][1], buy_date)
                if remaining > 1e-9:
                    return None
    if not days:
        return None
    return days
