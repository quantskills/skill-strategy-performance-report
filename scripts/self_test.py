#!/usr/bin/env python3
"""合成数据自检：验证绩效报告四模块、对账、净值重建与降级路径。

验证点：
  a) 区间收益 == 窗口内日收益乘积 − 1（独立重算）
  b) 累计收益 == nav[-1]/nav[0] − 1
  c) 最大回撤 == 植入的 −5% 单日，且 mdd_start==前一日、mdd_end==当日
  d) 年化波动 == std(daily_ret) × √252
  e) Sharpe（rf=0）== 公式手算
  f) 胜率 / 盈亏比 == 已知成交手工计数
  g) returns.recon_residual < 1e-6
  h) ECharts 交互 HTML 自包含（chart_* 容器 / echarts.init / 无外链 / 内嵌运行时）；options 纯 JSON
  i) 降级路径：无交易→trades/positions.degraded；全无→returns.degraded；无 pnl 且不可 FIFO→pnl_source="none"
  j) 重建路径：仅成交+持仓 → nav_source∈reconstructed_*，首值 1.0
  k) 缺图表守卫：charts=[] 时 render_html 仍产出合法 </html> + 降级横幅

运行：python scripts/self_test.py [--out out/self_test]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Windows GBK 控制台对 U+2212 等字符会报 UnicodeEncodeError，统一走 UTF-8
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

from performance import run_returns, run_risk, run_trades, run_positions, build_charts
from performance.base import Context, build_equity_curve
from report import render_markdown, render_json, timestamp
from html_report import render_html

SEED = 7


def build_nav(dates: pd.DatetimeIndex) -> pd.Series:
    """植入图案：除第 40 日外全部 +0.8%，第 40 日 −5.0%（唯一回撤 → MDD 可手算）。"""
    rng = np.random.default_rng(SEED)
    nav = pd.Series(1.0, index=dates, dtype=float)
    for i in range(1, len(dates)):
        if i == 40:
            r = -0.05
        else:
            r = 0.008 + rng.normal(0, 0.0005)
        nav.iloc[i] = nav.iloc[i - 1] * (1 + r)
    return nav


def build_benchmark(dates: pd.DatetimeIndex) -> pd.Series:
    rng = np.random.default_rng(SEED + 1)
    bench = pd.Series(1.0, index=dates, dtype=float)
    for i in range(1, len(dates)):
        bench.iloc[i] = bench.iloc[i - 1] * (1 + 0.003 + rng.normal(0, 0.002))
    return bench


def build_trades(dates: pd.DatetimeIndex) -> pd.DataFrame:
    """4 笔买入（pnl 0）+ 10 笔卖出：7 胜 +120、3 负 −80 → 胜率 0.7、盈亏比 3.5。"""
    rows = []
    symbols = ["S000", "S001", "S002"]
    # 买入（建立头寸，pnl 0）
    for k in range(4):
        rows.append((dates[3 + k], symbols[k % 3], "buy", 10.0 + k, 100, 0.0))
    # 卖出（7 胜 3 负）
    for k in range(10):
        pnl = 120.0 if k < 7 else -80.0
        rows.append((dates[8 + k * 4], symbols[k % 3], "sell", 10.0 + k, 100, pnl))
    return pd.DataFrame(rows, columns=["date", "symbol", "side", "price", "shares", "pnl"])


def build_positions(dates: pd.DatetimeIndex) -> pd.DataFrame:
    """三个标的的日市值，总量近似一条平稳曲线（重建路径用）。"""
    rows = []
    weights = [0.40, 0.35, 0.25]
    for i, d in enumerate(dates):
        total = 1.0 + 0.002 * i
        for s, w in zip(["S000", "S001", "S002"], weights):
            rows.append((d, s, total * w))
    return pd.DataFrame(rows, columns=["date", "symbol", "market_value"])


def _check(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(f"[FAIL] {msg}")
    print(f"[ok] {msg} [PASS]")


def main() -> int:
    ap = argparse.ArgumentParser(description="绩效报告自检（合成数据）")
    ap.add_argument("--out", default=os.path.join("out", "self_test"))
    args = ap.parse_args()

    dates = pd.bdate_range("2025-06-02", periods=250)
    nav = build_nav(dates)
    bench = build_benchmark(dates)
    trades = build_trades(dates)
    positions = build_positions(dates)

    ctx = Context(
        nav=nav, benchmark_nav=bench, trades=trades, positions=positions,
        frequency="monthly", benchmark_label="沪深300", scope="all", output_format="all",
        nav_source="user_nav", strategy_name="自检策略",
    )
    modules = {
        "returns": run_returns(ctx),
        "risk": run_risk(ctx),
        "trades": run_trades(ctx),
        "positions": run_positions(ctx),
    }

    rdata = modules["returns"].data
    riskdata = modules["risk"].data
    trdata = modules["trades"].data

    # a) 区间收益 == 窗口内日收益乘积 − 1
    s, e = pd.Timestamp(rdata["period_start"]), pd.Timestamp(rdata["period_end"])
    window = nav[(nav.index >= s) & (nav.index <= e)]
    window_rets = window.pct_change().dropna()
    expect_period = float(np.prod(1 + window_rets) - 1)
    _check(abs(rdata["period_return"] - expect_period) < 1e-9,
           f"区间收益对账 {rdata['period_return']:.6f} == {expect_period:.6f}")

    # b) 累计收益
    expect_cum = float(nav.iloc[-1] / nav.iloc[0] - 1)
    _check(abs(rdata["cumulative_return"] - expect_cum) < 1e-9,
           f"累计收益 {rdata['cumulative_return']:.6f} == {expect_cum:.6f}")

    # c) 最大回撤 == 植入 −5% 日
    _check(abs(riskdata["mdd"] - (-0.05)) < 1e-9, f"MDD {riskdata['mdd']:.6f} == -0.05")
    _check(str(pd.Timestamp(riskdata["mdd_start"]).date()) == str(dates[39].date()), "mdd_start == 回撤前一日")
    _check(str(pd.Timestamp(riskdata["mdd_end"]).date()) == str(dates[40].date()), "mdd_end == −5% 当日")
    _check(riskdata["mdd_recovery"] is not None, "mdd_recovery 已修复")

    # d) 年化波动
    daily = nav.pct_change().dropna()
    expect_vol = float(daily.std(ddof=1) * np.sqrt(ctx.annualization))
    _check(abs(riskdata["annualized_vol"] - expect_vol) < 1e-9,
           f"年化波动 {riskdata['annualized_vol']:.6f} == {expect_vol:.6f}")

    # e) Sharpe（rf=0）
    expect_sharpe = float(daily.mean() / daily.std(ddof=1) * np.sqrt(ctx.annualization))
    _check(abs(riskdata["sharpe"] - expect_sharpe) < 1e-9,
           f"Sharpe {riskdata['sharpe']:.4f} == {expect_sharpe:.4f}")

    # f) 胜率 / 盈亏比 == 手工计数
    _check(trdata["win_rate"] == 7 / 10, f"胜率 {trdata['win_rate']:.4f} == 0.7")
    _check(trdata["profit_factor"] == 840.0 / 240.0, f"盈亏比 {trdata['profit_factor']:.4f} == 3.5")
    _check(trdata["pnl_source"] == "pnl_column", f"PnL 口径 {trdata['pnl_source']} == pnl_column")

    # g) 对账
    _check(modules["returns"].recon_residual < 1e-6, f"收益对账残差 {modules['returns'].recon_residual:.2e} < 1e-6")

    # h) ECharts 交互 HTML 自包含（离线内嵌运行时，无外链）
    charts = build_charts(modules, ctx)
    ts = timestamp()
    html = render_html(modules, ctx, ts, charts)
    _check(len(charts) > 0, f"图表生成 {len(charts)} 张")
    _check('id="chart_equity_curve"' in html, "HTML 含 chart_equity_curve 容器")
    _check("echarts.init(" in html, "HTML 含 echarts.init 初始化")
    _check('<meta charset="utf-8">' in html, "HTML meta charset")
    _check("</html>" in html, "HTML 完整闭合 </html>")
    # 无外链资源：仅检查真实外部 URL（echarts.min.js 源码内部含 <img src 模板，非外链）
    _check('<script src' not in html and 'src="http' not in html and 'src="https' not in html
           and 'href="http' not in html and 'href="https' not in html,
           "HTML 无外链资源（离线内嵌 echarts.min.js）")
    _check(html.count("<script") >= 2, "HTML 内嵌 echarts 运行时 + 初始化脚本")
    for c in charts:
        json.dumps(c.option, ensure_ascii=False)  # options 必须纯 JSON
    _check(True, "图表 options 全部 JSON 可序列化")

    # k) 缺图表守卫：charts=[] → 表格型 HTML + 横幅
    html_no_charts = render_html(modules, ctx, ts, [])
    _check("</html>" in html_no_charts, "无图表时 HTML 仍合法 </html>")
    _check("已降级为表格" in html_no_charts, "无图表时显示降级横幅")

    # i) 降级路径
    ctx_nav_only = Context(nav=nav, frequency="monthly", scope="all")
    _check(run_trades(ctx_nav_only).degraded, "无成交 → trades 降级")
    _check(run_positions(ctx_nav_only).degraded, "无持仓 → positions 降级")

    ctx_empty = Context(nav=None, frequency="monthly", scope="all")
    nav_, src, note = build_equity_curve(ctx_empty)
    ctx_empty.nav, ctx_empty.nav_source, ctx_empty.nav_note = nav_, src, note
    _check(run_returns(ctx_empty).degraded, "全无 → returns 降级")

    sell_only = pd.DataFrame(
        [(dates[10], "S000", "sell", 10.0, 100), (dates[11], "S001", "sell", 11.0, 100)],
        columns=["date", "symbol", "side", "price", "shares"],
    )
    ctx_nopnl = Context(nav=nav, trades=sell_only, frequency="monthly", scope="all")
    bad = run_trades(ctx_nopnl)
    _check(bad.degraded and bad.data.get("pnl_source") == "none", "无 pnl 列且不可 FIFO → 交易降级 pnl_source=none")

    # j) 重建路径（方法 A 现金法：成交从第 3 日起，避免首日重复计）
    recon_trades = pd.DataFrame(
        [
            (dates[2], "S000", "buy", 10.0, 100),
            (dates[2], "S001", "buy", 10.0, 100),
            (dates[30], "S000", "sell", 10.5, 50),
            (dates[60], "S001", "sell", 9.8, 50),
        ],
        columns=["date", "symbol", "side", "price", "shares"],
    )
    ctx_recon = Context(nav=None, trades=recon_trades, positions=positions, frequency="monthly", scope="all")
    rnav, rsrc, rnote = build_equity_curve(ctx_recon)
    _check(rsrc in ("reconstructed_cash", "reconstructed_mv"), f"重建方法 {rsrc}")
    _check(rnav is not None and abs(float(rnav.iloc[0]) - 1.0) < 1e-12, "重建净值首值 == 1.0")
    ctx_recon.nav, ctx_recon.nav_source, ctx_recon.nav_note = rnav, rsrc, rnote
    _check(not run_returns(ctx_recon).degraded, "重建净值可出收益报告")

    # 渲染并写出报告 + 样例 CSV（供 CLI 端到端验证）
    os.makedirs(args.out, exist_ok=True)
    md = render_markdown(modules, ctx, ts, charts)
    js = render_json(modules, ctx, ts, charts)
    with open(os.path.join(args.out, "strategy_report.md"), "w", encoding="utf-8") as fh:
        fh.write(md)
    with open(os.path.join(args.out, "strategy_report.json"), "w", encoding="utf-8") as fh:
        json.dump(js, fh, ensure_ascii=False, indent=2)
    with open(os.path.join(args.out, "strategy_report.html"), "w", encoding="utf-8") as fh:
        fh.write(html)

    cli_input = os.path.join(args.out, "..", "cli_input")
    cli_input = os.path.normpath(cli_input)
    os.makedirs(cli_input, exist_ok=True)
    nav.rename("nav").reset_index().to_csv(os.path.join(cli_input, "nav.csv"), index=False)
    bench.rename("nav").reset_index().to_csv(os.path.join(cli_input, "benchmark.csv"), index=False)
    trades.to_csv(os.path.join(cli_input, "trades.csv"), index=False)
    positions.to_csv(os.path.join(cli_input, "positions.csv"), index=False)

    print(f"[ok] 报告 → {args.out}/strategy_report.html")
    print(f"[ok] 样例 CSV → {cli_input}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
