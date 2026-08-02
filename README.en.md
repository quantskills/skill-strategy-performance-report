# skill-strategy-performance-report

[简体中文](./README.md) | **English**

**Periodic performance report generator for LIVE A-share quant strategies**: daily / weekly / monthly / semi-annual / annual (and custom periods) health checks across four modules (returns, risk, trades, positions/turnover) with self-contained visualization — unified PerfReport (HTML + Markdown + JSON) with **return reconciliation**.

`role: skill` `output: PerfReport(html/md/json)` `paradigm: live strategy performance` `license: GPL-3.0`

---

`skill-strategy-performance-report` is a PandaAI Quant Skills (QUANTSKILLS org, category 05 Backtesting & Trading) **live-strategy performance report skill**. Given a live strategy's NAV / benchmark / trades / positions, it aggregates by frequency, computes four-module metrics, renders a self-contained HTML report (charts embedded as base64 PNG, viewable offline), and guarantees return reconciliation — **not a backtest framework, a live-performance report generator**.

It is the ecosystem's **first interactive-visualization skill**: 7 charts (equity curve vs benchmark, drawdown, monthly returns heatmap, rolling Sharpe, trade PnL distribution, period returns, position concentration) are **interactive ECharts** (hover tooltips / dataZoom / legend toggle); the runtime ships with the skill, so a single offline file renders fully without internet.

## 🎯 What it solves

For a running live strategy, answer on a cadence (daily/weekly/monthly/semi-annual/annual): *"how much did we make, what risk did we take, how did trading go, how are positions positioned"*:

- **Returns**: period return, cumulative, annualized, period-over-period table, benchmark comparison & excess
- **Risk**: max drawdown (with start/trough/recovery), annualized vol, Sharpe, Sortino, Calmar, rolling Sharpe
- **Trades**: win rate, profit factor, avg win/loss, PnL distribution (by period / by symbol), avg holding days
- **Positions/turnover**: current holdings, Top-N concentration, one-way turnover, rebalance count
- **Visualization**: 7 interactive ECharts + one-click offline HTML dashboard

No existing NAV? The skill **reconstructs the equity curve from trades + positions** (labeled approximate), or degrades with a clear note — never fabricates data.

## Four modules + charts

| Module | Method | Output | Verification |
|---|---|---|---|
| 1 Returns | period/cumulative/annualized, bucket table, benchmark & excess curve | `returns` | reconcile prod(1+r_t)≈nav_end/nav_start |
| 2 Risk | MDD (start/trough/recovery), vol, Sharpe, Sortino, Calmar, rolling | `risk` | hand-computable pattern |
| 3 Trades | win rate, profit factor, PnL distribution, holding days (pnl column → FIFO → degrade) | `trades` | known-trade PnL |
| 4 Positions | holdings, concentration, turnover, rebalance count | `positions` | weight-series check |
| Charts | equity/benchmark, drawdown, monthly heatmap, rolling Sharpe, PnL dist, period returns, concentration | `charts` | self-contained HTML assertion |

## ⚡ Workflow (8 steps)

```
1. Identify data mode: NAV / trades+positions only / neither; pick frequency & benchmark
2. Declare conventions: frequency, benchmark, risk-free rate, annualization, window, PnL basis
3. Build/reuse equity curve: use NAV if given; else reconstruct (cash-aware → fully-invested) with label
4. Compute returns + reconcile: period/cumulative/annualized/buckets + benchmark/excess
5. Risk metrics: MDD/vol/Sharpe/Sortino/Calmar/rolling (degrade if sample < 20 days)
6. Trade analysis: PnL basis (pnl column → FIFO → degrade), win rate/profit factor/distribution/holding days
7. Positions/turnover: holdings, concentration, one-way turnover, rebalance count
8. Render: ECharts options → self-contained HTML dashboard (KPI cards + interactive charts) + Markdown + JSON, with conclusion & compliance
```

## 🚀 Quick start

```bash
# Install (Claude Code / OpenClaw / Codex etc. with a skills dir)
cp -r skill-strategy-performance-report ~/.claude/skills/skill-strategy-performance-report

# Dependencies (pandas + numpy; the ECharts runtime ships inside the skill — no Python chart library needed)
python -m pip install -r scripts/requirements.txt

# With daily NAV: generate a monthly report (HTML + Markdown + JSON)
python scripts/strategy_report_cli.py \
  --nav equity.csv --benchmark benchmark.csv \
  --trades trades.csv --positions positions.csv \
  --frequency monthly --format all --out out/

# Trades + positions only: skill reconstructs the equity curve internally
python scripts/strategy_report_cli.py --trades trades.csv --positions positions.csv --frequency weekly --out out/

# Synthetic-data self-test (reconciliation / reconstruction / degradation assertions)
python scripts/self_test.py
```

```text
Trigger prompt 1: Generate this month's performance report for my live strategy with returns, drawdown, trade win rate, and charts.
Trigger prompt 2: Produce the weekly report for this strategy; data is under data/ (equity.csv, benchmark.csv, trades.csv).
Trigger prompt 3: I only have trade records and positions — reconstruct the NAV and produce a semi-annual report.
```

## 🗃️ Input requirements

- **Strategy NAV** (optional but recommended): `date, nav` (or `date, ret`)
- **Benchmark NAV** (optional): `date, nav`; benchmark options are labels only — the skill never fetches index data
- **Trades** (optional): `date, symbol, side, price, shares[, pnl][, commission]`; side accepts buy/sell/B/买/卖
- **Positions** (optional): `date, symbol, market_value` (or wide date×symbol)

Missing input degrades, never fabricates: no NAV & no positions → returns degraded; no pnl column & FIFO unmatchable → trades degraded; sample < 20 days → risk degraded.

## 📦 Structure

```text
skill-strategy-performance-report/
├── SKILL.md                        # core protocol (4 modules + 8-step workflow + reconciliation)
├── references/                     # report-metrics (heart) / report-format / visualization / source_boundary
├── scripts/
│   ├── strategy_report_cli.py      # CLI entry
│   ├── self_test.py                # synthetic-data self-test (recon/reconstruct/degrade assertions)
│   ├── report.py                   # Markdown / JSON rendering
│   ├── html_report.py              # self-contained HTML rendering (base64 charts)
│   ├── requirements.txt
│   └── performance/                # returns / risk / trades / positions / charts
└── agents/                         # openai.yaml / cursor-rule.mdc / portable-loader
```

## Relationship to existing skills (complementary, not duplicative)

| Existing skill | Cat | Its boundary | What this adds |
|---|---|---|---|
| `skill-backtest` | 05 | Defines the backtest protocol, produces backtest NAV | Periodic performance reports on **live** results; consumes its NAV CSV |
| `skill-performance-attribution` | 05 | Return **attribution** decomposition | Periodic 4-module health check; its decomposition feeds the conclusion |
| `skill-risk-model` | 05 | Risk **attribution** (vol decomposition) | Risk **measures & history** (MDD/Sharpe/Sortino/rolling) |
| `skill-trade-review` | 05 | Per-trade review | Aggregated trade statistics (win rate / profit factor / PnL dist / holding days) |
| `skill-market-daily-review` | 03 | Market-level daily review | Strategy-level periodic reports; market review as benchmark/context |

## 📐 Core constraints

| Constraint | Description |
|---|---|
| 🧮 Reconcile | Product of daily returns ≈ period return (< 1e-6); mismatch = bug |
| 📉 Degrade, don't fabricate | No NAV → reconstruct from trades+positions with label; neither → degrade |
| 🎨 Self-contained viz | Single-file HTML, offline, interactive ECharts inlined; no runtime → tables-only fallback |
| 📌 Conventions first | Declare frequency/benchmark/risk-free rate/annualization/window/PnL basis before computing |
| 🚫 No advice | Research-level facts & statistical summaries only |

## ⚠️ Disclaimer

Research-level performance reporting tool only. Ships no market data; NAV/benchmark/trades/positions come from the user, and data legality is the user's responsibility. Verifies no return claims and constitutes no investment advice. Reports reflect statistical summaries of the given materials + historical data, not future performance.

## 📜 License

This project is licensed under the GNU General Public License v3.0. See [LICENSE](LICENSE).

## 🐼 PandaAI / QUANTSKILLS Community

<div align="center">
  <img src="https://raw.githubusercontent.com/quantskills/.github/main/profile/assets/pandaai-community-qr.jpg" alt="PandaAI community QR" width="220">
  <br>
  <sub>Scan to join the PandaAI community for QUANTSKILLS skills, agent workflows, and quant research.</sub>
</div>
