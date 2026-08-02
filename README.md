# skill-strategy-performance-report

[简体中文](./README.md) | [English](./README.en.md)

**实盘 A 股量化策略周期性绩效报告生成器**：对实盘策略做日报/周报/月报/半年报/年报（含自定义区间）绩效体检，四模块（收益/风险/交易/持仓换手）+ 自包含可视化，输出统一绩效报告（HTML + Markdown + JSON）并做**收益对账**。

`role: skill` `output: PerfReport(html/md/json)` `paradigm: live strategy performance` `license: GPL-3.0`

---

`skill-strategy-performance-report` 是 PandaAI Quant Skills（QUANTSKILLS 组织，05 策略回测与交易工具类）提供的**实盘策略绩效报告 Skill**。给定实盘策略的净值 / 基准 / 成交 / 持仓数据，它按频率聚合、计算四模块指标、渲染自包含 HTML 仪表盘（交互式 ECharts 图表内嵌，离线可开），并保证收益对账——**不是回测框架，是实盘绩效报告生成器**。

它是 QUANTSKILLS 生态首个**带交互式可视化**的 skill：7 张图（净值 vs 基准、回撤、月度收益热图、滚动 Sharpe、交易 PnL 分布、分桶收益、持仓集中度）为 **ECharts 交互图表**（悬停 tooltip / dataZoom 缩放 / 图例开关），运行时随 skill 内嵌，单文件离线可看。

## 🎯 这个 Skill 解决什么问题

实盘策略跑起来之后，需要按节奏（日/周/月/半年/年）回答「这期赚了多少、风险多大、交易做得怎么样、仓位怎么摆」：

- **收益**：本期收益、累计收益、年化收益、分桶收益表、基准对比与超额
- **风险**：最大回撤（含起止/修复日）、年化波动、Sharpe、Sortino、Calmar、滚动 Sharpe
- **交易**：胜率、盈亏比、平均盈亏、PnL 分布（按桶/按标的）、平均持仓天数
- **持仓换手**：当前持仓、Top-N 集中度、单边换手、本期调仓次数
- **可视化**：7 张交互式 ECharts 图表 + 一键生成的离线 HTML 仪表盘

没有现成净值也不怕：**由成交 + 持仓自动重建净值**（标注「近似」），或明确降级提示，绝不编造数据。

## 四模块 + 图表

| 模块 | 方法 | 输出 | 数据验证脚本 |
|---|---|---|---|
| 1 收益 | 区间/累计/年化、分桶表、基准对比与超额曲线 | `returns` | 对账 prod(1+r_t)≈nav_end/nav_start |
| 2 风险 | MDD（含起止/修复）、波动、Sharpe、Sortino、Calmar、滚动 | `risk` | 手算图案对照 |
| 3 交易 | 胜率、盈亏比、PnL 分布、持仓天数（pnl 列→FIFO→降级） | `trades` | 已知成交 PnL 对照 |
| 4 持仓换手 | 当前持仓、集中度、单边换手、调仓次数 | `positions` | 权重序列对照 |
| 图 | 净值 vs 基准 / 回撤 / 月度热图 / 滚动 Sharpe / PnL 分布 / 分桶收益 / 集中度 | `charts` | 自包含 HTML 断言 |

## ⚡ 工作流（标准 8 步）

```
1. 明确数据模式：有 NAV / 只有成交+持仓 / 两者皆无，选定频率与基准
2. 声明口径：频率、基准、无风险利率、年化、区间窗口、PnL 口径
3. 构建/复用净值曲线：有 NAV 直接用；无则重建（现金法→满仓法）并标注
4. 收益计算 + 对账：区间/累计/年化/分桶 + 基准对比与超额，日收益乘积对账
5. 风险指标：MDD/波动/Sharpe/Sortino/Calmar/滚动（样本 < 20 日降级）
6. 交易分析：PnL 口径（pnl 列→FIFO→降级）、胜率/盈亏比/分布/持仓天数
7. 持仓与换手：当前持仓、集中度、单边换手、调仓次数
8. 渲染：ECharts option → 内嵌自包含 HTML 仪表盘（KPI 卡片 + 交互图）+ Markdown + JSON，附结论与合规声明
```

## 🚀 快速开始

```bash
# 安装（Claude Code / OpenClaw / Codex 等支持 skills 目录的平台）
cp -r skill-strategy-performance-report ~/.claude/skills/skill-strategy-performance-report

# 依赖（pandas + numpy；图表运行时 ECharts 随 skill 内嵌，无需任何 Python 图表库）
python -m pip install -r scripts/requirements.txt

# 有日频净值：直接生成月报（HTML + Markdown + JSON）
python scripts/strategy_report_cli.py \
  --nav equity.csv --benchmark benchmark.csv \
  --trades trades.csv --positions positions.csv \
  --frequency monthly --format all --out out/

# 只有成交+持仓：skill 内部重建净值再出报告
python scripts/strategy_report_cli.py --trades trades.csv --positions positions.csv --frequency weekly --out out/

# 合成数据自检（含对账/重建/降级断言）
python scripts/self_test.py
```

```text
触发示例 prompt 1：给我实盘策略出本月绩效报告，包含收益、回撤、交易胜率和可视化。
触发示例 prompt 2：生成这份策略的周报，数据在 data/ 目录（equity.csv、benchmark.csv、trades.csv）。
触发示例 prompt 3：只有成交流水和持仓，帮我重建净值并出一份半年报。
```

## 🗃️ 输入要求

- **策略净值**（可选但推荐）：`date, nav`（或 `date, ret`）
- **基准净值**（可选）：`date, nav`；基准选项只是标签，skill 从不拉取指数
- **成交记录**（可选）：`date, symbol, side, price, shares[, pnl][, commission]`；side 支持 buy/sell/B/买/卖
- **持仓市值**（可选）：`date, symbol, market_value`（或宽表 date×symbol）

缺输入不臆测：无净值且无持仓 → 收益模块降级；成交缺 pnl 列且无法 FIFO 配平 → 交易模块降级；样本 < 20 日 → 风险模块降级。

## 📦 目录结构

```text
skill-strategy-performance-report/
├── SKILL.md                        # 核心协议（四模块 + 8 步工作流 + 对账纪律）
├── references/                     # report-metrics(心脏) / report-format / visualization / source_boundary
├── scripts/
│   ├── strategy_report_cli.py      # 绩效报告 CLI 入口
│   ├── self_test.py                # 合成数据自检（含对账/重建/降级断言）
│   ├── report.py                   # Markdown / JSON 渲染
│   ├── html_report.py              # 自包含 HTML 渲染（base64 图表内嵌）
│   ├── requirements.txt
│   └── performance/                # 四模块 + 图表（returns/risk/trades/positions/charts）
└── agents/                         # openai.yaml / cursor-rule.mdc / portable-loader
```

## 与既有 skill 的关系（互补不重复）

| 既有 skill | 分类 | 它的边界 | 本 skill 补什么 |
|---|---|---|---|
| `skill-backtest` | 05 | 定义回测协议、产回测净值 | 对**实盘**结果做周期化绩效报告；直接消费其净值 CSV |
| `skill-performance-attribution` | 05 | 收益**归因**分解 | 定期体检四模块；其归因可作「结论」素材 |
| `skill-risk-model` | 05 | 风险**归因**（波动分解） | 风险**度量与历史**（MDD/Sharpe/Sortino/滚动） |
| `skill-trade-review` | 05 | 逐笔交易复盘 | 聚合统计交易分析（胜率/盈亏比/PnL 分布/持仓天数） |
| `skill-market-daily-review` | 03 | 市场级日报 | 策略级周期报告；市场综述可作基准/背景 |

## 📐 核心约束

| 约束 | 说明 |
|---|---|
| 🧮 对账必过 | 日收益乘积 ≈ 区间收益（< 1e-6），对不上就是 bug |
| 📉 缺料降级不臆测 | 无净值→成交+持仓重建并标注；两者皆无→降级；绝不编造 |
| 🎨 可视化自包含 | HTML 单文件、离线、ECharts 交互图内嵌；运行时缺失→表格型降级 |
| 📌 口径先行 | 频率/基准/无风险利率/年化/窗口/PnL 口径计算前必须声明 |
| 🚫 只述不荐 | 输出研究层面的结构与事实归纳，不构成投资建议 |

## ⚠️ 免责声明

本仓库仅作量化研究方法层面的绩效报告工具。不附带任何市场数据；净值/基准/成交/持仓由使用者提供，数据合法性与许可由使用者负责。不验证任何收益声明，不构成任何投资建议。报告仅反映对给定材料 + 历史数据的统计归纳，不代表未来表现。

## 📜 License

This project is licensed under the GNU General Public License v3.0. See [LICENSE](LICENSE).

## 🐼 PandaAI / QUANTSKILLS 社群

<div align="center">
  <img src="https://raw.githubusercontent.com/quantskills/.github/main/profile/assets/pandaai-community-qr.jpg" alt="PandaAI 社群二维码" width="220">
  <br>
  <sub>扫码加入 PandaAI 社群，交流 QUANTSKILLS 技能、Agent 工作流与量化研究实践。</sub>
</div>
