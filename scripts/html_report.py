"""自包含 HTML 仪表盘报告渲染：KPI 卡片 + 锚点导航 + 美化表格 + 交互式 ECharts。

与 report.py 共享 _fmt/_pct/_money 与数据来源（同一 PerfResult.data）。
运行时 echarts.min.js 内嵌自 vendored assets/echarts.min.js（Apache-2.0，随 skill 分发）；
缺失时回退 CDN script 标签。charts 为空 → 表格型 HTML + 降级横幅，绝不出坏图。
"""
from __future__ import annotations

import html as _html
import json
import os

from report import FREQ_LABEL, COMPLIANCE, _fmt, _pct, _money

# 参考调色板（dataviz）与报表表面
SURFACE = "#fcfcfb"
PAGE = "#f9f9f7"
INK = "#0b0b0b"
SECONDARY = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BLUE = "#2a78d6"
ORANGE = "#eb6834"
RED = "#e34948"
GOOD = "#006300"
BAD = "#d03b3b"

CSS = f"""
:root {{ color-scheme: light; }}
* {{ box-sizing: border-box; }}
html {{ scroll-behavior: smooth; }}
body {{ margin: 0; background: {PAGE}; color: {INK};
       font-family: system-ui, -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif;
       line-height: 1.6; }}
.wrap {{ max-width: 1060px; margin: 0 auto; padding: 28px 20px 64px; }}
header.top {{ display: flex; justify-content: space-between; align-items: flex-end; flex-wrap: wrap;
              gap: 12px; margin-bottom: 18px; }}
h1 {{ font-size: 23px; margin: 0 0 4px; }}
.meta {{ color: {SECONDARY}; font-size: 13px; }}
nav.nav {{ position: sticky; top: 0; z-index: 10; background: rgba(252,252,251,.94);
           backdrop-filter: blur(4px); border-bottom: 1px solid {GRID};
           padding: 8px 2px; margin: 0 0 20px; font-size: 13px; }}
nav.nav a {{ color: {SECONDARY}; text-decoration: none; margin-right: 18px; }}
nav.nav a:hover {{ color: {BLUE}; }}
.kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 12px; margin: 0 0 22px; }}
.kpi {{ background: {SURFACE}; border: 1px solid {GRID}; border-radius: 8px; padding: 12px 14px; }}
.kpi .k-label {{ color: {SECONDARY}; font-size: 12px; }}
.kpi .k-value {{ font-size: 21px; font-weight: 600; margin-top: 2px; font-variant-numeric: tabular-nums; }}
.kpi .k-sub {{ color: {MUTED}; font-size: 11px; }}
.v-up {{ color: {RED}; }} .v-down {{ color: {BLUE}; }}
.card {{ background: {SURFACE}; border: 1px solid {GRID}; border-radius: 8px;
        padding: 18px 20px; margin: 0 0 18px; }}
h2 {{ font-size: 16px; margin: 0 0 12px; color: {INK}; }}
table {{ border-collapse: collapse; width: 100%; font-size: 13px; margin: 6px 0 4px; }}
th, td {{ text-align: right; padding: 7px 10px; border-bottom: 1px solid {GRID}; }}
tbody tr:nth-child(even) {{ background: #fafaf8; }}
th {{ font-weight: 600; color: {SECONDARY}; }}
td:first-child, th:first-child {{ text-align: left; }}
.chart {{ margin: 0 0 20px; }}
.chart figcaption {{ color: {SECONDARY}; font-size: 12px; margin: 4px 2px 0; }}
.note {{ color: {SECONDARY}; font-size: 13px; }}
.degraded {{ color: {BAD}; font-size: 13px; }}
.conclusion {{ font-size: 14px; background: #f4f7fb; border: 1px solid {GRID}; border-radius: 8px;
               padding: 12px 16px; }}
.banner {{ background: #fff7e6; border: 1px solid #f0d9a8; border-radius: 6px;
          padding: 10px 14px; font-size: 13px; color: {SECONDARY}; margin: 10px 0; }}
.compliance {{ margin-top: 30px; padding-top: 14px; border-top: 1px solid {GRID};
               color: {MUTED}; font-size: 12px; }}
"""


def _esc(s) -> str:
    return _html.escape(str(s) if s is not None else "—")


def _table(headers, rows) -> str:
    out = ['<table><thead><tr>' + "".join(f"<th>{_esc(h)}</th>" for h in headers) + '</tr></thead><tbody>']
    for row in rows:
        out.append('<tr>' + "".join(f"<td>{_esc(v)}</td>" for v in row) + '</tr>')
    out.append('</tbody></table>')
    return "".join(out)


def _runtime_script() -> str:
    """内嵌 vendored echarts.min.js（离线单文件）；缺失时回退 CDN script 标签。"""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    vendored = os.path.join(root, "assets", "echarts.min.js")
    if os.path.exists(vendored):
        with open(vendored, encoding="utf-8") as fh:
            return "<script>\n" + fh.read() + "\n</script>"
    return '<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>'


def _kpis(modules, ctx) -> str:
    ret = modules.get("returns")
    risk = modules.get("risk")
    trades = modules.get("trades")
    rdata = ret.data if ret is not None else {}

    period = rdata.get("period_return")
    period_cls = "v-up" if period is not None and period >= 0 else ("v-down" if period is not None else "")

    def tile(label, value, cls="", sub=None):
        return (f'<div class="kpi"><div class="k-label">{_esc(label)}</div>'
                f'<div class="k-value {cls}">{_esc(value)}</div>'
                + (f'<div class="k-sub">{_esc(sub)}</div>' if sub else '') + '</div>')

    tiles = [tile("本期收益", _pct(period), period_cls, f"{rdata.get('period_start','—')} ~ {rdata.get('period_end','—')}")]
    ann = rdata.get("annualized_return")
    tiles.append(tile("年化收益", _pct(ann), "v-up" if ann is not None and ann >= 0 else ("v-down" if ann is not None else ""), "几何 252 交易日"))
    if risk is not None and not risk.degraded:
        mdd = risk.data.get("mdd")
        tiles.append(tile("最大回撤", _pct(mdd), "v-down", f"{risk.data.get('mdd_start','—')} ~ {risk.data.get('mdd_end','—')}"))
        tiles.append(tile("Sharpe", _fmt(risk.data.get("sharpe"), 2), "", f"Sortino {_fmt(risk.data.get('sortino'), 2)}"))
    else:
        tiles.append(tile("最大回撤", "—"))
        tiles.append(tile("Sharpe", "—"))
    if trades is not None and not trades.degraded and trades.data.get("win_rate") is not None:
        tiles.append(tile("交易胜率", _pct(trades.data.get("win_rate")), "", f"盈亏比 {_fmt(trades.data.get('profit_factor'), 2)}"))
    else:
        tiles.append(tile("交易胜率", "—"))
    return '<div class="kpis">' + "".join(tiles) + '</div>'


def render_html(modules, ctx, generated_at: str, charts) -> str:
    ret = modules.get("returns")
    risk = modules.get("risk")
    trades = modules.get("trades")
    positions = modules.get("positions")
    rdata = ret.data if ret is not None else {}
    freq = FREQ_LABEL.get(ctx.frequency, "本区间")

    body: list[str] = []
    body.append('<header class="top">'
                f'<div><h1>A股策略绩效报告 · {_esc(ctx.strategy_name)}</h1>'
                f'<div class="meta">生成：{generated_at}　频率：{ctx.frequency}　基准：{_esc(ctx.benchmark_label)}　范围：{ctx.scope}</div></div>'
                '</header>')

    body.append('<nav class="nav">'
                '<a href="#s0">0 口径</a><a href="#s1">1 收益</a><a href="#s2">2 风险</a>'
                '<a href="#s3">3 交易</a><a href="#s4">4 持仓</a><a href="#charts">图表</a>'
                '</nav>')

    body.append(_kpis(modules, ctx))

    # 0. 口径声明
    rows = [
        ("报告区间", f"{rdata.get('period_start', '—')} ~ {rdata.get('period_end', '—')}"),
        ("净值来源", rdata.get("nav_source", "—")),
        ("无风险利率（年化）", _fmt(ctx.risk_free_rate, 4)),
        ("年化交易日", str(ctx.annualization)),
        ("滚动 Sharpe 窗口", f"{ctx.rolling_sharpe_window} 日"),
    ]
    if rdata.get("nav_note"):
        rows.append(("净值说明", rdata["nav_note"]))
    if rdata.get("window_fallback"):
        rows.append(("区间退化", "自定义区间未提供，按最近一个月处理"))
    if trades is not None and trades.data.get("pnl_source"):
        rows.append(("交易 PnL 口径", trades.data["pnl_source"]))
    body.append(f'<section class="card" id="s0"><h2>0. 口径声明</h2>{_table(["口径", "取值"], rows)}</section>')

    # 1. 收益
    s1 = ['<section class="card" id="s1"><h2>1. 收益</h2>']
    if ret is not None and ret.degraded:
        s1.append(f'<div class="degraded">（降级：{_esc(ret.note)}）</div>')
    else:
        rows = [
            (f"{freq}收益", _pct(rdata.get("period_return"))),
            ("累计收益（自策略起点）", _pct(rdata.get("cumulative_return"))),
            (f"年化收益（几何，{ctx.annualization} 交易日）", _pct(rdata.get("annualized_return"))),
            ("区间交易日数", rdata.get("n_window_days", "—")),
        ]
        b = rdata.get("benchmark")
        if b:
            rows += [
                (f"基准（{b['benchmark_label']}）{freq}收益", _pct(b.get("bench_period_return"))),
                ("超额收益（算术）", _pct(b.get("excess_arithmetic"))),
                ("超额收益（相对）", _pct(b.get("excess_relative"))),
            ]
        s1.append(_table(["指标", "值"], rows))
        buckets = rdata.get("period_over_period") or []
        if buckets:
            s1.append(_table(["分桶", "收益"], [(b["bucket"], _pct(b["ret"])) for b in buckets]))
        recon = rdata.get("recon_residual")
        recon_ok = recon is not None and recon < 1e-6
        s1.append(f'<div class="note">对账：日收益乘积与区间收益残差 = {_fmt(recon, 6)}　'
                  f'<span class="{"ok" if recon_ok else "degraded"}">{"通过（< 1e-6）" if recon_ok else "未通过，存在 bug"}</span></div>')
        if rdata.get("benchmark_note"):
            s1.append(f'<div class="note">（基准说明：{_esc(rdata["benchmark_note"])}）</div>')
    s1.append('</section>')
    body.append("".join(s1))

    # 2. 风险
    s2 = ['<section class="card" id="s2"><h2>2. 风险</h2>']
    if risk is not None and risk.degraded:
        s2.append(f'<div class="degraded">（降级：{_esc(risk.note)}）</div>')
    else:
        rd = risk.data
        rows = [
            ("最大回撤", _pct(rd.get("mdd"))),
            ("回撤区间", f"{rd.get('mdd_start', '—')} ~ {rd.get('mdd_end', '—')}（修复日 {rd.get('mdd_recovery', '未修复')}）"),
            ("年化波动率", _pct(rd.get("annualized_vol"))),
            ("Sharpe", _fmt(rd.get("sharpe"), 3)),
            ("Sortino", _fmt(rd.get("sortino"), 3)),
            ("Calmar", _fmt(rd.get("calmar"), 3)),
            ("滚动 Sharpe（最新）", _fmt(rd.get("rolling_sharpe_latest"), 3)),
            ("最优日", f"{rd.get('best_day', {}).get('date', '—')}（{_pct(rd.get('best_day', {}).get('ret'))}）"),
            ("最差日", f"{rd.get('worst_day', {}).get('date', '—')}（{_pct(rd.get('worst_day', {}).get('ret'))}）"),
            ("样本交易日", rd.get("n_days", "—")),
        ]
        s2.append(_table(["指标", "值"], rows))
    s2.append('</section>')
    body.append("".join(s2))

    # 3. 交易分析
    s3 = ['<section class="card" id="s3"><h2>3. 交易分析</h2>']
    if trades is not None and trades.degraded and "pnl_list" not in trades.data:
        s3.append(f'<div class="degraded">（降级：{_esc(trades.note)}）</div>')
    else:
        td = trades.data
        s3.append(f'<div class="note">PnL 口径：{_esc(td.get("pnl_source", "—"))}</div>')
        hd = td.get("holding_days")
        rows = [
            ("成交笔数", td.get("total_trades", "—")),
            ("平仓笔数", td.get("closed_trades", "—")),
            ("胜率", _pct(td.get("win_rate"))),
            ("盈亏比", _fmt(td.get("profit_factor"), 3)),
            ("平均盈利", _money(td.get("avg_win"))),
            ("平均亏损", _money(td.get("avg_loss"))),
        ]
        if hd:
            rows.append(("平均持仓天数（营业日近似）", _fmt(sum(hd) / len(hd), 1)))
        s3.append(_table(["指标", "值"], rows))
        if td.get("pnl_by_period"):
            s3.append(_table(["分桶", "PnL"], [(b["bucket"], _money(b["pnl"])) for b in td["pnl_by_period"]]))
        if td.get("pnl_by_symbol"):
            s3.append(_table(["标的", "笔数", "PnL"], [(b["symbol"], b["n"], _money(b["pnl"])) for b in td["pnl_by_symbol"]]))
        if trades.degraded:
            s3.append(f'<div class="degraded">（注意：{_esc(trades.note)}）</div>')
    s3.append('</section>')
    body.append("".join(s3))

    # 4. 持仓与换手
    s4 = ['<section class="card" id="s4"><h2>4. 持仓与换手</h2>']
    if positions is not None and positions.degraded:
        s4.append(f'<div class="degraded">（降级：{_esc(positions.note)}）</div>')
    else:
        pd_ = positions.data
        s4.append(f'<div class="note">截至 {_esc(pd_.get("as_of", "—"))}：持仓 {pd_.get("n_holdings", "—")} 只，'
                  f'总市值 {_money(pd_.get("total_market_value"))}</div>')
        holdings = pd_.get("current_holdings") or []
        if holdings:
            s4.append(_table(["标的", "市值", "权重"], [(h["symbol"], _money(h["market_value"]), _pct(h["weight"])) for h in holdings]))
        s4.append(_table(
            ["指标", "值"],
            [
                (f"Top-{pd_.get('top_n', '—')} 集中度", _pct(pd_.get("top_n_concentration"))),
                ("单边换手（区间均值）", _pct(pd_.get("one_way_turnover"))),
                ("本期调仓交易日数", _fmt(pd_.get("rebalance_count"), 0)),
            ],
        ))
    s4.append('</section>')
    body.append("".join(s4))

    # 图表（交互式 ECharts）
    if charts:
        divs = []
        for c in charts:
            divs.append(f'<figure class="chart"><div id="chart_{c.key}" style="width:100%;height:380px"></div>'
                        f'<figcaption>{_esc(c.title)}</figcaption></figure>')
        init = "".join(
            f"echarts.init(document.getElementById('chart_{c.key}'), null, {{renderer:'canvas'}})"
            f".setOption({json.dumps(c.option, ensure_ascii=False).replace('</', '<\\\\/')});\n"
            for c in charts
        )
        body.append(f'<section class="card" id="charts"><h2>图表</h2>{"".join(divs)}</section>')
        body.append(f"<script>\n{init}</script>")
    elif ctx.output_format in ("all", "html"):
        body.append('<div class="banner">（图表运行时不可用，已降级为表格）</div>')

    # 5. 结论
    if ret is not None and not ret.degraded:
        parts = [f"{freq}策略收益 {_pct(rdata.get('period_return'))}"]
        b = rdata.get("benchmark")
        if b and b.get("excess_arithmetic") is not None:
            ex = b["excess_arithmetic"]
            parts.append(("跑赢" if ex >= 0 else "跑输") + f"基准 {_pct(abs(ex))}")
        if risk is not None and not risk.degraded:
            parts.append(f"期间最大回撤 {_pct(risk.data.get('mdd'))}")
        if trades is not None and not trades.degraded and trades.data.get("win_rate") is not None:
            parts.append(f"交易胜率 {_pct(trades.data.get('win_rate'))}")
        body.append(f'<section class="card" id="s5"><h2>5. 结论</h2><div class="conclusion">{"；".join(parts)}。</div></section>')
    else:
        body.append(f'<section class="card" id="s5"><h2>5. 结论</h2><div class="note">（数据不足，本期无法给出结论。）</div></section>')

    # 6. 合规声明
    body.append(f'<div class="compliance">{_esc(COMPLIANCE)}</div>')

    runtime = _runtime_script() if charts else ""
    return (
        "<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head>\n"
        '<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>绩效报告 · {_esc(ctx.strategy_name)}</title>\n"
        f"<style>{CSS}</style>\n</head>\n<body>\n"
        f'<div class="wrap">\n{"\n".join(body)}\n</div>\n{runtime}\n</body>\n</html>'
    )
