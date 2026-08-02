"""图表模块：产出 ECharts option（纯 JSON，生态首个交互式可视化）。

设计约定（对齐 dataviz 方法论，颜色来自验证过的参考调色板）：
- 类别色按固定顺序分配：策略=蓝 #2a78d6、基准=橙 #eb6834；从不循环生成新色相
- 分叉（极性）蓝↔红 + 中性灰 #f0efec；A股习惯红=涨/正收益，蓝=跌/负收益
- 单一 y 轴（净值/基准归一化到 1.0）；tooltip/十字线/图例开关/dataZoom 交互相交
- option 为纯 JSON（list/str/float/bool/None），无函数、无 numpy/pandas 对象；
  运行时 echarts.min.js 由 html_report.py 内嵌（vendored，Apache-2.0）

Chart.option 构建不依赖任何 Python 图表库 —— 永远可生成，仅缺失 JS 运行时会影响查看。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

# —— 参考调色板（dataviz，浅色表面）——
SERIES_BLUE = "#2a78d6"
SERIES_ORANGE = "#eb6834"
SERIES_RED = "#e34948"
DIVERGING_MID = "#f0efec"
AXIS = "#898781"


@dataclass
class Chart:
    key: str
    title: str
    option: dict


def _jnum(x) -> float | None:
    """转为 JSON 安全数值：NaN → None，round 到 6 位。"""
    if x is None:
        return None
    try:
        if pd.isna(x):
            return None
    except (TypeError, ValueError):
        pass
    return round(float(x), 6)


def _cats(series: pd.Series) -> list[str]:
    return [str(d.date()) for d in series.index]


def _nums(series: pd.Series) -> list[float | None]:
    return [_jnum(v) for v in series.values]


def _grid() -> dict:
    return {"left": 60, "right": 20, "top": 40, "bottom": 60}


def _markline_zero() -> dict:
    return {"data": [{"yAxis": 0}], "lineStyle": {"type": "dashed", "color": AXIS}}


def _line_series(name: str, cats, vals, color: str, width: float = 2.0, area: bool = False) -> dict:
    s = {
        "name": name,
        "type": "line",
        "data": vals,
        "smooth": True,
        "showSymbol": False,
        "lineStyle": {"width": width},
        "itemStyle": {"color": color},
    }
    if area:
        s["areaStyle"] = {"opacity": 0.22, "color": color}
    return s


def _bar_data(vals, pos_color: str = SERIES_RED, neg_color: str = SERIES_BLUE) -> list[dict]:
    return [{"value": v, "itemStyle": {"color": pos_color if v >= 0 else neg_color}} for v in vals]


def _chart_equity(modules, ctx) -> Chart | None:
    ret = modules.get("returns")
    nav = ret.series.get("nav") if ret is not None else None
    if nav is None or len(nav) == 0:
        return None
    cats = _cats(nav)
    nnorm = nav.div(nav.iloc[0])
    series = [_line_series("策略", cats, _nums(nnorm), SERIES_BLUE)]
    legend = ["策略"]
    bnorm = ret.series.get("bench_norm")
    if bnorm is not None:
        series.append(_line_series(ctx.benchmark_label, _cats(bnorm), _nums(bnorm), SERIES_ORANGE, width=1.5))
        legend.append(ctx.benchmark_label)
    option = {
        "color": [SERIES_BLUE, SERIES_ORANGE],
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "cross"}},
        "legend": {"data": legend, "top": 0},
        "grid": _grid(),
        "xAxis": {"type": "category", "data": cats, "boundaryGap": False},
        "yAxis": {"type": "value", "scale": True, "name": "净值（归一 1.0）"},
        "dataZoom": [{"type": "inside"}, {"type": "slider", "height": 18}],
        "series": series,
    }
    return Chart("equity_curve", "净值 vs 基准（归一化 1.0）", option)


def _chart_drawdown(modules, ctx) -> Chart | None:
    risk = modules.get("risk")
    dd = risk.series.get("drawdown") if risk is not None else None
    if dd is None or len(dd) == 0:
        return None
    option = {
        "color": [SERIES_RED],
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "cross"}},
        "grid": _grid(),
        "xAxis": {"type": "category", "data": _cats(dd), "boundaryGap": False},
        "yAxis": {"type": "value", "name": "回撤 %", "max": 0},
        "series": [{
            "name": "回撤",
            "type": "line",
            "data": [None if v is None else round(v * 100, 2) for v in _nums(dd)],
            "smooth": True,
            "showSymbol": False,
            "lineStyle": {"width": 1, "color": SERIES_RED},
            "areaStyle": {"opacity": 0.25, "color": SERIES_RED},
            "markLine": _markline_zero(),
        }],
    }
    return Chart("drawdown", "回撤曲线", option)


def _chart_monthly_returns(modules, ctx) -> Chart | None:
    ret = modules.get("returns")
    nav = ret.series.get("nav") if ret is not None else None
    if nav is None or len(nav) < 20:
        return None
    rets = nav.pct_change().dropna()
    if len(rets) == 0:
        return None
    mdf = pd.DataFrame({"ret": rets.values}, index=rets.index)
    mdf["year"] = mdf.index.year
    mdf["month"] = mdf.index.month
    piv = mdf.groupby(["year", "month"])["ret"].apply(lambda x: float(np.prod(1 + x) - 1)).unstack(fill_value=0.0)
    months = list(range(1, 13))
    years = sorted(piv.index.tolist())
    max_abs = max(1.0, float(np.nanmax(np.abs(piv.values))) * 100)
    data = []
    for yi, year in enumerate(years):
        for mi, month in enumerate(months):
            v = piv.loc[year, month] if month in piv.columns else 0.0
            data.append([mi, len(years) - 1 - yi, round(float(v) * 100, 2)])
    option = {
        "tooltip": {"trigger": "item"},
        "grid": _grid(),
        "xAxis": {"type": "category", "data": [f"{m}月" for m in months], "splitArea": {"show": True}},
        "yAxis": {"type": "category", "data": [str(y) for y in reversed(years)], "splitArea": {"show": True}},
        "visualMap": {
            "min": -max_abs,
            "max": max_abs,
            "calculable": True,
            "orient": "horizontal",
            "left": "center",
            "bottom": 0,
            "inRange": {"color": [SERIES_BLUE, DIVERGING_MID, SERIES_RED]},
            "text": ["正", "负"],
        },
        "series": [{"name": "月度收益", "type": "heatmap", "data": data}],
    }
    return Chart("monthly_returns", "月度收益热图（%）", option)


def _chart_rolling_sharpe(modules, ctx) -> Chart | None:
    risk = modules.get("risk")
    rs = risk.series.get("rolling_sharpe") if risk is not None else None
    if rs is None or len(rs.dropna()) == 0:
        return None
    option = {
        "color": [SERIES_BLUE],
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "cross"}},
        "grid": _grid(),
        "xAxis": {"type": "category", "data": _cats(rs), "boundaryGap": False},
        "yAxis": {"type": "value", "name": "Sharpe"},
        "series": [_line_series("滚动 Sharpe", _cats(rs), _nums(rs), SERIES_BLUE)],
    }
    option["series"][0]["markLine"] = _markline_zero()
    return Chart("rolling_sharpe", f"滚动 Sharpe（窗口 {ctx.rolling_sharpe_window} 日）", option)


def _chart_trade_pnl(modules, ctx) -> Chart | None:
    trades = modules.get("trades")
    pnl_list = trades.data.get("pnl_list") if trades is not None else None
    if not pnl_list:
        return None
    arr = np.asarray([float(x) for x in pnl_list])
    arr = arr[arr != 0] if np.any(arr != 0) else arr
    if len(arr) == 0:
        return None
    counts, edges = np.histogram(arr, bins=20)
    labels = [f"{int((edges[i] + edges[i + 1]) / 2)}" for i in range(len(counts))]
    data = []
    for i, c in enumerate(counts):
        center = (edges[i] + edges[i + 1]) / 2
        data.append({"value": int(c), "itemStyle": {"color": SERIES_RED if center >= 0 else SERIES_BLUE}})
    option = {
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        "grid": _grid(),
        "xAxis": {"type": "category", "data": labels, "name": "PnL"},
        "yAxis": {"type": "value", "name": "笔数"},
        "series": [{"type": "bar", "data": data, "barWidth": "60%"}],
    }
    return Chart("trade_pnl", "交易 PnL 分布", option)


def _chart_period_returns(modules, ctx) -> Chart | None:
    ret = modules.get("returns")
    buckets = ret.data.get("period_over_period") if ret is not None else None
    if not buckets:
        return None
    labels = [b["bucket"] for b in buckets]
    vals = [round(float(b["ret"]) * 100, 2) for b in buckets]
    option = {
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        "grid": _grid(),
        "xAxis": {"type": "category", "data": labels, "axisLabel": {"rotate": 45, "fontSize": 10}},
        "yAxis": {"type": "value", "name": "收益 %"},
        "series": [{"type": "bar", "data": _bar_data(vals), "barWidth": "60%",
                    "markLine": _markline_zero()}],
    }
    return Chart("period_returns", f"分桶区间收益（%，{ctx.frequency}）", option)


def _chart_concentration(modules, ctx) -> Chart | None:
    positions = modules.get("positions")
    holdings = positions.data.get("current_holdings") if positions is not None else None
    if not holdings:
        return None
    top = holdings[: ctx.top_n]
    symbols = [h["symbol"] for h in top][::-1]
    weights = [round(float(h["weight"] or 0) * 100, 2) for h in top][::-1]
    option = {
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        "grid": {"left": 70, "right": 30, "top": 20, "bottom": 40},
        "xAxis": {"type": "value", "name": "权重 %"},
        "yAxis": {"type": "category", "data": symbols},
        "series": [{"type": "bar", "data": weights, "itemStyle": {"color": SERIES_BLUE}, "barWidth": "60%"}],
    }
    return Chart("concentration", "Top-N 持仓权重（%）", option)


_BUILDERS = [
    _chart_equity,
    _chart_drawdown,
    _chart_monthly_returns,
    _chart_rolling_sharpe,
    _chart_trade_pnl,
    _chart_period_returns,
    _chart_concentration,
]


def build_charts(modules: dict, ctx) -> list[Chart]:
    """构建 7 张图的 ECharts option。无数据/模块降级时对应图跳过。

    option 为纯 JSON，构建永不因缺库失败（仅查看 HTML 需 echarts.min.js 运行时）。
    """
    charts: list[Chart] = []
    for builder in _BUILDERS:
        try:
            c = builder(modules, ctx)
        except Exception as exc:  # noqa: BLE001 —— 单图失败不阻塞其余
            print(f"[warn] 图表 {getattr(builder, '__name__', '?')} 异常：{exc}")
            continue
        if c is not None:
            charts.append(c)
    return charts
