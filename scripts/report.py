"""报告渲染：把模块结果渲染为 Markdown 与 JSON。

格式契约见 references/report-format.md。
"""
from __future__ import annotations

import datetime

FREQ_LABEL = {
    "daily": "报告期",
    "weekly": "本周",
    "monthly": "本月",
    "semi_annual": "本半年",
    "annual": "本年度",
    "custom": "本区间",
}

COMPLIANCE = "仅供量化研究、教育与方法论参考，不构成任何形式的投资建议、交易信号或获利保证。"


def timestamp() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d")


def _fmt(x, nd=4) -> str:
    return "—" if x is None else f"{x:.{nd}f}"


def _pct(x, nd=2) -> str:
    return "—" if x is None else f"{x * 100:.{nd}f}%"


def _money(x, nd=2) -> str:
    return "—" if x is None else f"{x:,.{nd}f}"


def _mdd_pct(x) -> str:
    return "—" if x is None else f"{x * 100:.2f}%"


# ---------- Markdown ----------

def render_markdown(modules, ctx, generated_at: str, charts=None) -> str:
    lines: list[str] = []
    ret = modules.get("returns")
    risk = modules.get("risk")
    trades = modules.get("trades")
    positions = modules.get("positions")
    rdata = ret.data if ret is not None else {}
    freq = FREQ_LABEL.get(ctx.frequency, "本区间")

    lines.append("# A股策略绩效报告")
    lines.append("")
    lines.append(f"> 生成：{generated_at}　策略：{ctx.strategy_name}　频率：{ctx.frequency}　基准：{ctx.benchmark_label}")
    lines.append("")

    # 0. 口径声明
    lines.append("## 0. 口径声明")
    lines.append("")
    lines.append("| 口径 | 取值 |")
    lines.append("|---|---|")
    lines.append(f"| 报告区间 | {rdata.get('period_start', '—')} ~ {rdata.get('period_end', '—')} |")
    lines.append(f"| 净值来源 | {rdata.get('nav_source', '—')} |")
    if rdata.get("nav_note"):
        lines.append(f"| 净值说明 | {rdata['nav_note']} |")
    lines.append(f"| 无风险利率（年化） | {_fmt(ctx.risk_free_rate, 4)} |")
    lines.append(f"| 年化交易日 | {ctx.annualization} |")
    lines.append(f"| 滚动 Sharpe 窗口 | {ctx.rolling_sharpe_window} 日 |")
    if rdata.get("window_fallback"):
        lines.append("| 区间退化 | 自定义区间未提供，按最近一个月处理 |")
    if trades is not None and trades.data.get("pnl_source"):
        lines.append(f"| 交易 PnL 口径 | {trades.data['pnl_source']} |")
    lines.append("")

    # 1. 收益
    lines.append("## 1. 收益")
    lines.append("")
    if ret is not None and ret.degraded:
        lines.append(f"_（降级：{ret.note}）_")
        lines.append("")
    else:
        lines.append("| 指标 | 值 |")
        lines.append("|---|---|")
        lines.append(f"| {freq}收益 | {_pct(rdata.get('period_return'))} |")
        lines.append(f"| 累计收益（自策略起点） | {_pct(rdata.get('cumulative_return'))} |")
        lines.append(f"| 年化收益（几何，{ctx.annualization} 交易日） | {_pct(rdata.get('annualized_return'))} |")
        lines.append(f"| 区间交易日数 | {rdata.get('n_window_days', '—')} |")
        if rdata.get("benchmark"):
            b = rdata["benchmark"]
            lines.append(f"| 基准（{b['benchmark_label']}）{freq}收益 | {_pct(b.get('bench_period_return'))} |")
            lines.append(f"| 超额收益（算术） | {_pct(b.get('excess_arithmetic'))} |")
            lines.append(f"| 超额收益（相对） | {_pct(b.get('excess_relative'))} |")
        lines.append("")
        lines.append("**分桶收益**")
        lines.append("")
        buckets = rdata.get("period_over_period") or []
        if buckets:
            lines.append("| 分桶 | 收益 |")
            lines.append("|---|---|")
            for b in buckets:
                lines.append(f"| {b['bucket']} | {_pct(b['ret'])} |")
        else:
            lines.append("_（区间内分桶样本不足，未生成分桶收益表）_")
        lines.append("")
        lines.append(f"**对账**：日收益乘积与区间收益残差 = {_fmt(rdata.get('recon_residual'), 6)}"
                     + ("（< 1e-6，通过）" if (rdata.get('recon_residual') is not None and rdata['recon_residual'] < 1e-6) else "（未通过，存在 bug）"))
        if rdata.get("benchmark_note"):
            lines.append("")
            lines.append(f"_（基准说明：{rdata['benchmark_note']}）_")
        lines.append("")

    # 2. 风险
    lines.append("## 2. 风险")
    lines.append("")
    if risk is not None and risk.degraded:
        lines.append(f"_（降级：{risk.note}）_")
        lines.append("")
    else:
        rd = risk.data
        lines.append("| 指标 | 值 |")
        lines.append("|---|---|")
        lines.append(f"| 最大回撤 | {_mdd_pct(rd.get('mdd'))} |")
        lines.append(f"| 回撤区间 | {rd.get('mdd_start', '—')} ~ {rd.get('mdd_end', '—')}（修复日 {rd.get('mdd_recovery', '未修复')}） |")
        lines.append(f"| 年化波动率 | {_pct(rd.get('annualized_vol'))} |")
        lines.append(f"| Sharpe | {_fmt(rd.get('sharpe'), 3)} |")
        lines.append(f"| Sortino | {_fmt(rd.get('sortino'), 3)} |")
        lines.append(f"| Calmar | {_fmt(rd.get('calmar'), 3)} |")
        lines.append(f"| 滚动 Sharpe（最新，窗口 {ctx.rolling_sharpe_window} 日） | {_fmt(rd.get('rolling_sharpe_latest'), 3)} |")
        if rd.get("best_day"):
            lines.append(f"| 最优日 | {rd['best_day']['date']}（{_pct(rd['best_day']['ret'])}） |")
        if rd.get("worst_day"):
            lines.append(f"| 最差日 | {rd['worst_day']['date']}（{_pct(rd['worst_day']['ret'])}） |")
        lines.append(f"| 样本交易日 | {rd.get('n_days', '—')} |")
        lines.append("")

    # 3. 交易分析
    lines.append("## 3. 交易分析")
    lines.append("")
    if trades is not None and trades.degraded and "pnl_list" not in trades.data:
        lines.append(f"_（降级：{trades.note}）_")
        lines.append("")
    else:
        td = trades.data
        lines.append(f"**PnL 口径**：{td.get('pnl_source', '—')}")
        lines.append("")
        lines.append("| 指标 | 值 |")
        lines.append("|---|---|")
        lines.append(f"| 成交笔数 | {td.get('total_trades', '—')} |")
        lines.append(f"| 平仓笔数 | {td.get('closed_trades', '—')} |")
        lines.append(f"| 胜率 | {_pct(td.get('win_rate'))} |")
        lines.append(f"| 盈亏比 | {_fmt(td.get('profit_factor'), 3)} |")
        lines.append(f"| 平均盈利 | {_money(td.get('avg_win'))} |")
        lines.append(f"| 平均亏损 | {_money(td.get('avg_loss'))} |")
        if td.get("holding_days"):
            hd = td["holding_days"]
            lines.append(f"| 平均持仓天数（营业日近似） | {_fmt(sum(hd) / len(hd), 1)} |")
        lines.append("")
        if td.get("pnl_by_period"):
            lines.append("**分桶 PnL**")
            lines.append("")
            lines.append("| 分桶 | PnL |")
            lines.append("|---|---|")
            for b in td["pnl_by_period"]:
                lines.append(f"| {b['bucket']} | {_money(b['pnl'])} |")
            lines.append("")
        if td.get("pnl_by_symbol"):
            lines.append("**按标的 PnL**")
            lines.append("")
            lines.append("| 标的 | 笔数 | PnL |")
            lines.append("|---|---|---|")
            for b in td["pnl_by_symbol"]:
                lines.append(f"| {b['symbol']} | {b['n']} | {_money(b['pnl'])} |")
            lines.append("")
        if trades.degraded:
            lines.append(f"_（注意：{trades.note}）_")
            lines.append("")

    # 4. 持仓与换手
    lines.append("## 4. 持仓与换手")
    lines.append("")
    if positions is not None and positions.degraded:
        lines.append(f"_（降级：{positions.note}）_")
        lines.append("")
    else:
        pd_ = positions.data
        lines.append(f"**截至 {pd_.get('as_of', '—')}**：持仓 {pd_.get('n_holdings', '—')} 只，总市值 {_money(pd_.get('total_market_value'))}")
        lines.append("")
        holdings = pd_.get("current_holdings") or []
        if holdings:
            lines.append("| 标的 | 市值 | 权重 |")
            lines.append("|---|---|---|")
            for h in holdings:
                lines.append(f"| {h['symbol']} | {_money(h['market_value'])} | {_pct(h['weight'])} |")
            lines.append("")
        lines.append(f"| 指标 | 值 |")
        lines.append("|---|---|")
        lines.append(f"| Top-{pd_.get('top_n', '—')} 集中度 | {_pct(pd_.get('top_n_concentration'))} |")
        lines.append(f"| 单边换手（区间均值） | {_pct(pd_.get('one_way_turnover'))} |")
        lines.append(f"| 本期调仓交易日数 | {_fmt(pd_.get('rebalance_count'), 0)} |")
        lines.append("")

    # 图表（交互式，位于 HTML；Markdown 只留指引）
    if charts:
        lines.append("## 图表")
        lines.append("")
        lines.append("> 图表为交互式 ECharts（" + "、".join(c.title for c in charts) + "），见同目录 `strategy_report.html`。")
        lines.append("")

    # 5. 结论
    lines.append("## 5. 结论")
    lines.append("")
    if ret is not None and not ret.degraded:
        parts = [f"{freq}策略收益 {_pct(rdata.get('period_return'))}"]
        b = rdata.get("benchmark")
        if b and b.get("excess_arithmetic") is not None:
            ex = b["excess_arithmetic"]
            parts.append(("跑赢" if ex >= 0 else "跑输") + f"基准 {_pct(abs(ex))}")
        if risk is not None and not risk.degraded:
            parts.append(f"期间最大回撤 {_mdd_pct(risk.data.get('mdd'))}")
        if trades is not None and not trades.degraded and trades.data.get("win_rate") is not None:
            parts.append(f"交易胜率 {_pct(trades.data.get('win_rate'))}")
        lines.append(f"{'；'.join(parts)}。")
    else:
        lines.append("（数据不足，本期无法给出结论。）")
    lines.append("")

    # 6. 合规声明
    lines.append("## 6. 合规声明")
    lines.append("")
    lines.append(COMPLIANCE)
    lines.append("")

    return "\n".join(lines)


# ---------- JSON ----------

def render_json(modules, ctx, generated_at: str, charts=None) -> dict:
    ret = modules.get("returns")
    reconciled = bool(ret is not None and ret.recon_residual is not None and ret.recon_residual < 1e-6)
    return {
        "schema": "skill-strategy-performance-report/1",
        "generated_at": generated_at,
        "meta": {
            "strategy_name": ctx.strategy_name,
            "frequency": ctx.frequency,
            "benchmark": ctx.benchmark_label,
            "risk_free_rate": ctx.risk_free_rate,
            "annualization": ctx.annualization,
            "rolling_sharpe_window": ctx.rolling_sharpe_window,
            "nav_source": ctx.nav_source,
        },
        "modules": {k: v.to_dict() for k, v in modules.items()},
        # JSON 只带图表键引用（base64 体积大，图表本体在 HTML / Markdown 中）
        "charts": [{"key": c.key, "title": c.title} for c in charts] if charts else [],
        "reconciled": reconciled,
    }
