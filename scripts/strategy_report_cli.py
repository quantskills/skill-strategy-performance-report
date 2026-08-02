#!/usr/bin/env python3
"""实盘策略绩效报告 CLI（协议 + 可运行脚本的入口）。

用法：
  python scripts/strategy_report_cli.py \
      --nav equity.csv --benchmark benchmark.csv \
      --trades trades.csv --positions positions.csv \
      --frequency monthly --format all --out out/

  # 只有成交+持仓：skill 内部重建净值
  python scripts/strategy_report_cli.py --trades trades.csv --positions positions.csv --frequency weekly --out out/

输入约定见 performance/base.py。缺输入 → 对应模块降级，绝不臆测。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Windows GBK 控制台对 U+2212 等字符会报 UnicodeEncodeError，统一走 UTF-8
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

from performance import build_charts, run_returns, run_risk, run_trades, run_positions
from performance.base import Context, build_equity_curve, load_equity, load_benchmark, load_trades, load_positions
from report import render_markdown, render_json, timestamp
from html_report import render_html

FREQUENCIES = ["daily", "weekly", "monthly", "semi_annual", "annual", "custom"]
SCOPES = ["all", "returns", "risk", "trades", "positions"]
FORMATS = ["all", "html", "md"]


def main() -> int:
    ap = argparse.ArgumentParser(description="实盘 A 股策略周期性绩效报告")
    ap.add_argument("--nav", help="日频净值（date, nav[|ret]）")
    ap.add_argument("--benchmark", help="基准净值（date, nav[|ret]）")
    ap.add_argument("--trades", help="成交记录（date, symbol, side, price, shares[, pnl][, commission]）")
    ap.add_argument("--positions", help="持仓市值（date, symbol, market_value[, ...]）或宽表 date×symbol")
    ap.add_argument("--initial-cash", type=float, default=None, help="净值重建期初现金（缺省锚定 1.0）")
    ap.add_argument("--frequency", default="weekly", choices=FREQUENCIES, help="报告频率")
    ap.add_argument("--start", default=None, help="自定义区间起始 YYYY-MM-DD")
    ap.add_argument("--end", default=None, help="自定义区间结束 YYYY-MM-DD")
    ap.add_argument("--benchmark-label", default="自定义", help="基准显示名")
    ap.add_argument("--risk-free-rate", type=float, default=0.0, help="无风险利率（年化）")
    ap.add_argument("--annualization", type=int, default=252, help="年化交易日数")
    ap.add_argument("--rolling-sharpe-window", type=int, default=60, help="滚动 Sharpe 窗口")
    ap.add_argument("--top-n", type=int, default=10, help="集中度 Top-N")
    ap.add_argument("--name", default="实盘策略", help="策略名")
    ap.add_argument("--scope", default="all", choices=SCOPES, help="报告范围")
    ap.add_argument("--format", default="all", choices=FORMATS, help="输出格式")
    ap.add_argument("--out", default="out", help="输出目录")
    args = ap.parse_args()

    ctx = Context(
        nav=load_equity(args.nav),
        benchmark_nav=load_benchmark(args.benchmark),
        trades=load_trades(args.trades),
        positions=load_positions(args.positions),
        initial_cash=args.initial_cash,
        frequency=args.frequency,
        custom_start=args.start,
        custom_end=args.end,
        benchmark_label=args.benchmark_label,
        risk_free_rate=args.risk_free_rate,
        annualization=args.annualization,
        rolling_sharpe_window=args.rolling_sharpe_window,
        top_n=args.top_n,
        scope=args.scope,
        output_format=args.format,
        strategy_name=args.name,
    )

    # 净值：有则直接用，无则重建（returns 模块也依赖 ctx.nav 已就位）
    if ctx.nav is None or len(ctx.nav) == 0:
        nav, src, note = build_equity_curve(ctx)
        ctx.nav, ctx.nav_source, ctx.nav_note = nav, src, note
    else:
        ctx.nav_source = "user_nav"

    modules = {}
    if args.scope in ("all", "returns"):
        modules["returns"] = run_returns(ctx)
    if args.scope in ("all", "risk"):
        modules["risk"] = run_risk(ctx)
    if args.scope in ("all", "trades"):
        modules["trades"] = run_trades(ctx)
    if args.scope in ("all", "positions"):
        modules["positions"] = run_positions(ctx)

    charts = build_charts(modules, ctx) if args.format in ("all", "html") else []

    os.makedirs(args.out, exist_ok=True)
    ts = timestamp()
    md = render_markdown(modules, ctx, ts, charts)
    js = render_json(modules, ctx, ts, charts)
    with open(os.path.join(args.out, "strategy_report.md"), "w", encoding="utf-8") as fh:
        fh.write(md)
    with open(os.path.join(args.out, "strategy_report.json"), "w", encoding="utf-8") as fh:
        json.dump(js, fh, ensure_ascii=False, indent=2)

    html_path = None
    if args.format in ("all", "html"):
        html_path = os.path.join(args.out, "strategy_report.html")
        with open(html_path, "w", encoding="utf-8") as fh:
            fh.write(render_html(modules, ctx, ts, charts))

    status = [f"{k}=[OK]" if (v is not None and not v.degraded) else f"{k}=[degraded]" for k, v in modules.items()]
    target = html_path or os.path.join(args.out, "strategy_report.md")
    print(f"[ok] 绩效报告完成：{', '.join(status)} -> {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
