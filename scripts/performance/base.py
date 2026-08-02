"""共享基础：Context、PerfResult、输入加载、净值重建。

依赖：pandas + numpy（无 scipy）。图表为 ECharts option（纯 JSON），运行时 echarts.min.js 由 html_report.py 内嵌（vendored，Apache-2.0）。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

ANNUALIZATION_DEFAULT = 252

# 默认假设（判定基线，对齐生态 skill-backtest 协议精神）
DEFAULT_ASSUMPTIONS = {
    "risk_free_rate": 0.0,
    "annualization": 252,
    "rolling_sharpe_window": 60,
    "top_n": 10,
    "min_sample_days": 20,
}

# side 归一化别名
BUY_ALIASES = {"buy", "b", "买", "买入"}
SELL_ALIASES = {"sell", "s", "卖", "卖出"}
NAV_COLUMNS = ("nav", "equity", "nav_value", "value", "net_value")
RET_COLUMNS = ("ret", "return", "ret_daily", "daily_return")

VERDICTS = ("OK", "DEGRADED")


def _sanitize(obj):
    """把 data 递归转成 JSON 可序列化的 Python 原生类型（numpy/pandas 兜底）。"""
    if isinstance(obj, dict):
        return {str(k): _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, np.generic):
        return obj.item()
    if isinstance(obj, (np.ndarray, pd.Series)):
        return [_sanitize(v) for v in obj.tolist()]
    if isinstance(obj, pd.Timestamp):
        return str(obj)
    return obj


@dataclass
class PerfResult:
    """模块结果。data 仅存 JSON 可序列化值；series 供 charts 使用，不进 JSON。"""

    name: str
    data: dict = field(default_factory=dict)
    series: dict = field(default_factory=dict)
    recon_residual: float | None = None
    degraded: bool = False
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "data": _sanitize(self.data),
            "recon_residual": self.recon_residual,
            "degraded": self.degraded,
            "note": self.note,
        }


@dataclass
class Context:
    nav: pd.Series | None = None            # date -> nav（权威）
    benchmark_nav: pd.Series | None = None  # date -> nav
    trades: pd.DataFrame | None = None      # date, symbol, side, price, shares[, pnl][, commission]
    positions: pd.DataFrame | None = None   # date, symbol, market_value
    initial_cash: float | None = None       # 净值重建期初现金；None 锚定 1.0
    frequency: str = "weekly"               # daily|weekly|monthly|semi_annual|annual|custom
    custom_start: str | None = None
    custom_end: str | None = None
    benchmark_label: str = "未指定"
    risk_free_rate: float = 0.0
    annualization: int = ANNUALIZATION_DEFAULT
    rolling_sharpe_window: int = 60
    top_n: int = 10
    min_sample_days: int = 20
    scope: str = "all"                      # all|returns|risk|trades|positions
    output_format: str = "all"              # all|html|md
    strategy_name: str = "实盘策略"
    nav_source: str = "user_nav"            # user_nav|reconstructed_cash|reconstructed_mv|none
    nav_note: str = ""


# ---------- 输入加载 ----------

def _read(path: str) -> pd.DataFrame:
    lower = path.lower()
    if lower.endswith((".csv", ".txt")):
        return pd.read_csv(path)
    if lower.endswith((".parquet", ".pq")):
        return pd.read_parquet(path)
    if lower.endswith((".xlsx", ".xls")):
        return pd.read_excel(path)
    raise ValueError(f"不支持的输入格式: {path}")


def _to_nav_series(df: pd.DataFrame) -> pd.Series:
    """宽表/长表 → date 索引的净值序列。识别 nav/equity 列，或 ret 列 cumprod。"""
    df = df.copy()
    date_col = "date" if "date" in df.columns else df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col]).set_index(date_col).sort_index()
    nav_col = next((c for c in NAV_COLUMNS if c in df.columns), None)
    if nav_col is None:
        ret_col = next((c for c in RET_COLUMNS if c in df.columns), None)
        if ret_col is None:
            raise ValueError(f"净值文件缺少 nav/equity 或 ret 列：{list(df.columns)}")
        series = (1.0 + df[ret_col].astype(float)).cumprod()
    else:
        series = df[nav_col].astype(float)
    series = series[~series.index.duplicated(keep="last")]
    return series.rename("nav").astype(float)


def load_equity(path: str | None) -> pd.Series | None:
    if not path or not os.path.exists(path):
        return None
    return _to_nav_series(_read(path))


def load_benchmark(path: str | None) -> pd.Series | None:
    return load_equity(path)


def load_trades(path: str | None) -> pd.DataFrame | None:
    if not path or not os.path.exists(path):
        return None
    df = _read(path)
    for c in ("date", "symbol", "side", "price", "shares"):
        if c not in df.columns:
            raise ValueError(f"成交文件缺少列：{c}（需要 date,symbol,side,price,shares）")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    df["side"] = df["side"].astype(str).str.strip().str.lower()
    df["buy"] = df["side"].isin(BUY_ALIASES)
    df["sell"] = df["side"].isin(SELL_ALIASES)
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["shares"] = pd.to_numeric(df["shares"], errors="coerce")
    df = df.dropna(subset=["price", "shares"])
    if "pnl" in df.columns:
        df["pnl"] = pd.to_numeric(df["pnl"], errors="coerce")
    if "commission" in df.columns:
        df["commission"] = pd.to_numeric(df["commission"], errors="coerce")
    return df.sort_values("date").reset_index(drop=True)


def ensure_trade_cols(df: pd.DataFrame | None) -> pd.DataFrame | None:
    """确保成交表带 buy/sell 布尔列（供 FIFO 与净值重建使用）。

    load_trades 已加列；直接构造 Context.trades 的调用方由本函数兜底。
    """
    if df is None or len(df) == 0:
        return df
    if "buy" in df.columns and "sell" in df.columns:
        return df
    df = df.copy()
    side = df["side"].astype(str).str.strip().str.lower()
    df["buy"] = side.isin(BUY_ALIASES)
    df["sell"] = side.isin(SELL_ALIASES)
    return df


def load_positions(path: str | None) -> pd.DataFrame | None:
    """持仓：长表（date, symbol, market_value[, ...]）或宽表 date×symbol → 长表。"""
    if not path or not os.path.exists(path):
        return None
    df = _read(path)
    if "date" not in df.columns:
        raise ValueError("持仓文件需要 date 列")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    if "symbol" in df.columns:
        if "market_value" not in df.columns:
            raise ValueError("持仓长表需要 market_value 列")
        out = df[["date", "symbol", "market_value"]].copy()
    else:
        out = df.set_index("date").stack().rename("market_value").reset_index()
        out.columns = ["date", "symbol", "market_value"]
    out["market_value"] = pd.to_numeric(out["market_value"], errors="coerce")
    out = out.dropna(subset=["market_value"]).sort_values(["date", "symbol"]).reset_index(drop=True)
    return out


# ---------- 净值重建 ----------

def build_equity_curve(ctx: Context) -> tuple[pd.Series | None, str, str]:
    """返回 (nav, method, note)。优先级：用户 NAV → 重建（现金法→满仓法）→ None。

    重建为**近似**：假设持仓市值完整、现金变动全来自成交；缺省初始现金锚定 1.0，
    使报告展示收益表现而非绝对 PnL。
    """
    if ctx.nav is not None and len(ctx.nav) > 0:
        return ctx.nav, "user_nav", ""
    if ctx.positions is None or len(ctx.positions) == 0:
        return None, "none", "缺少净值或成交+持仓，无法构建净值曲线"
    dates = pd.DatetimeIndex(sorted(ctx.positions["date"].unique()))
    if len(dates) == 0:
        return None, "none", "持仓数据为空"
    mv = ctx.positions.groupby("date")["market_value"].sum().reindex(dates).fillna(0.0)
    if ctx.trades is not None and len(ctx.trades) > 0:
        trades = ensure_trade_cols(ctx.trades).copy()
        trades["cash_flow"] = np.where(
            trades["buy"], -trades["price"] * trades["shares"], trades["price"] * trades["shares"]
        )
        if "commission" in trades.columns:
            trades["cash_flow"] = trades["cash_flow"] - trades["commission"].fillna(0.0)
        cf = trades.groupby("date")["cash_flow"].sum().reindex(dates).fillna(0.0)
        mv0 = float(mv.iloc[0])
        cash0 = (1.0 - mv0) if ctx.initial_cash is None else float(ctx.initial_cash) - mv0
        cash = cash0 + cf.cumsum()
        equity = mv + cash
        method = "reconstructed_cash"
        note = "净值由成交+持仓重建（现金法，近似）"
    else:
        equity = mv
        method = "reconstructed_mv"
        note = "净值由持仓市值重建（满仓法，近似）"
    e0 = float(equity.iloc[0])
    nav = equity / e0 if e0 != 0 else equity
    return nav.rename("nav").astype(float), method, note
