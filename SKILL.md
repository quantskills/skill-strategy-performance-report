---
name: strategy-performance-report
description: Use when an agent needs to generate a periodic performance report for a LIVE A-share quant strategy — 日报/周报/月报/半年报/年报 or custom period — covering returns, risk, trade analysis, and position/turnover detail, with embedded visualizations. Outputs a self-contained offline HTML dashboard (interactive ECharts) plus Markdown + JSON.
quantSkills:
  organization: https://github.com/quantskills
  repository: wangofcong/skill-strategy-performance-report
  repository_url: https://github.com/wangofcong/skill-strategy-performance-report
  project_type: skill
  collection: 策略回测与交易工具
  license: GPL-3.0
  category: tooling
  tags:
  - performance-report
  - sharpe
  - drawdown
  - turnover
  - equity-curve
  - live-monitoring
  - visualization
  platforms:
  - claude-code
  - codex
  - openclaw
  - cursor
  language: zh-en
  status: stable
  validation_level: listed
  maintainer_type: community
  requires: []
  summary_zh: 实盘 A 股量化策略周期性绩效报告：四模块（收益/风险/交易/持仓换手）覆盖日报/周报/月报/半年报/年报，支持自定义区间；无净值时由成交+持仓重建净值；输出自包含离线 HTML 仪表盘（交互式 ECharts 图表内嵌）+ Markdown + JSON，并对账。
  summary_en: Periodic performance reports for live A-share quant strategies across daily/weekly/monthly/semi-annual/annual and custom periods — four modules (returns, risk, trades, positions/turnover); reconstructs the equity curve from trades+positions when no NAV is given; outputs a self-contained offline HTML dashboard (interactive ECharts) plus Markdown + JSON with reconciliation.
---

```json qsh-form
{
  "version": 1,
  "task": {
    "placeholder": "粘贴策略说明 / 本期关注点（可选），或补充自定义区间的起止日期",
    "required": false
  },
  "fields": [
    {
      "key": "frequency",
      "type": "select",
      "label": "报告频率",
      "default": "monthly",
      "options": [
        { "value": "daily", "label": "日报" },
        { "value": "weekly", "label": "周报" },
        { "value": "monthly", "label": "月报" },
        { "value": "semi_annual", "label": "半年报" },
        { "value": "annual", "label": "年报" },
        { "value": "custom", "label": "自定义区间" }
      ]
    },
    {
      "key": "benchmark",
      "type": "select",
      "label": "基准",
      "default": "000300.SH",
      "options": [
        { "value": "000300.SH", "label": "沪深300" },
        { "value": "000905.SH", "label": "中证500" },
        { "value": "000852.SH", "label": "中证1000" },
        { "value": "custom", "label": "自定义" },
        { "value": "none", "label": "无基准" }
      ]
    },
    {
      "key": "risk_free_rate",
      "type": "number",
      "label": "无风险利率（年化）",
      "default": "0.0",
      "help": "Sharpe/Sortino 用；A股量化基线默认 0"
    },
    {
      "key": "report_scope",
      "type": "select",
      "label": "报告范围",
      "default": "all",
      "options": [
        { "value": "all", "label": "四模块全开（推荐）" },
        { "value": "returns", "label": "仅收益" },
        { "value": "risk", "label": "仅风险" },
        { "value": "trades", "label": "仅交易分析" },
        { "value": "positions", "label": "仅持仓与换手" }
      ]
    },
    {
      "key": "output_format",
      "type": "select",
      "label": "输出格式",
      "default": "all",
      "options": [
        { "value": "all", "label": "HTML + Markdown + JSON" },
        { "value": "html", "label": "HTML（Markdown 仅指向图表）" },
        { "value": "md", "label": "仅 Markdown + JSON（图表见 HTML）" }
      ]
    },
    {
      "key": "custom_start",
      "type": "date",
      "label": "自定义区间起始",
      "default": "",
      "help": "frequency=custom 时必填"
    },
    {
      "key": "custom_end",
      "type": "date",
      "label": "自定义区间结束",
      "default": "",
      "help": "frequency=custom 时必填"
    },
    {
      "key": "file_paths",
      "type": "textarea",
      "label": "数据文件路径（NAV/基准/成交/持仓）",
      "placeholder": "每行一个：equity.csv, benchmark.csv, trades.csv, positions.csv；缺哪个自动降级",
      "help": "仅给出文件路径，不粘贴数据；NAV 有就用 NAV，否则由成交+持仓重建"
    }
  ],
  "prompt_template": "{{#task}}任务与材料：\n{{task}}\n\n{{/task}}{{#attachments}}用户上传的材料（已放入工作区）：\n{{attachments}}\n\n{{/attachments}}请为 A 股实盘量化策略生成绩效报告：频率 {{frequency}}，基准 {{benchmark}}，无风险利率 {{risk_free_rate}}，范围 {{report_scope}}，输出格式 {{output_format}}{{#custom_start}}，自定义区间 {{custom_start}} 至 {{custom_end}}{{/custom_start}}。数据文件：{{file_paths}}（NAV/基准/成交/持仓，缺则自动降级，绝不臆测）。覆盖收益、风险、交易、持仓四模块，对账通过后输出自包含 HTML + Markdown + JSON，中文输出。"
}
```

# Strategy Performance Report

> 对**实盘 A 股量化策略**做周期性绩效体检（日报/周报/月报/半年报/年报/自定义区间）：四模块（收益/风险/交易/持仓换手）+ 自包含可视化，输出统一绩效报告（HTML + Markdown + JSON）并做**对账**。**不是回测框架，是实盘绩效报告生成器**。

## 核心规则

1. **口径先行**：频率、基准、无风险利率、年化（252）、区间窗口在计算前必须声明
2. **对账必过**：窗口内日收益乘积 ≈ 区间收益（残差 < 1e-6），对不上就是 bug
3. **缺料降级不臆测**：无净值 → 由成交+持仓重建并标注；两者皆无 → 降级提示，绝不编造
4. **只述不荐**：报告呈现事实与统计归纳，不构成投资建议
5. **可视化自包含**：HTML 单文件、离线、ECharts 交互图内嵌；运行时缺失 → 降级为表格型 HTML

## 四模块 + 图表

| 模块 | 方法 | 输出 | 数据验证脚本 |
|---|---|---|---|
| 1 收益 | 区间/累计/年化收益、分桶收益表、基准对比与超额曲线 | `returns` | 对账 prod(1+r_t)≈nav_end/nav_start |
| 2 风险 | 最大回撤（含起止/修复）、年化波动、Sharpe、Sortino、Calmar、滚动 Sharpe | `risk` | 手算图案对照 |
| 3 交易 | 胜率、盈亏比、平均盈亏、PnL 分布（按桶/按标的）、持仓天数 | `trades` | 已知成交 PnL 对照 |
| 4 持仓换手 | 当前持仓表、Top-N 集中度、单边换手、本期调仓次数 | `positions` | 权重序列对照 |
| 图 | 净值 vs 基准 / 回撤 / 月度收益热图 / 滚动 Sharpe / PnL 分布 / 区间收益 / 集中度 | `charts`（base64 PNG） | 自包含 HTML 断言 |

公式与口径见 `references/report-metrics.md`（心脏文档）及 `references/visualization.md`。

## 工作流（标准 8 步）

```
1. 明确数据模式：有 NAV / 只有成交+持仓 / 两者皆无，选定频率与基准
2. 声明口径：频率、基准、无风险利率、年化、区间窗口、成本与 PnL 口径
3. 构建/复用净值曲线：有 NAV 直接用；无则按重建规则（现金法→满仓法）
4. 收益计算 + 对账：区间/累计/年化/分桶 + 基准对比与超额，日收益乘积对账
5. 风险指标：MDD/波动/Sharpe/Sortino/Calmar/滚动（样本 < 20 日降级）
6. 交易分析：PnL 口径（pnl 列→FIFO→降级）、胜率/盈亏比/分布/持仓天数
7. 持仓与换手：当前持仓、集中度、单边换手、调仓次数
8. 渲染：ECharts option → 内嵌自包含 HTML 仪表盘（KPI 卡片 + 交互图）+ Markdown + JSON，附结论与合规声明
```

## 脚本用法（可运行绩效报告）

```bash
# 有日频净值：直接生成月报（HTML + Markdown + JSON）
python scripts/strategy_report_cli.py \
  --nav equity.csv --benchmark benchmark.csv \
  --trades trades.csv --positions positions.csv \
  --frequency monthly --format all --out out/

# 只有成交+持仓：skill 内部重建净值再出报告
python scripts/strategy_report_cli.py \
  --trades trades.csv --positions positions.csv --frequency weekly --out out/

# 合成数据自检（含对账/重建/降级断言）
python scripts/self_test.py
```

缺输入不臆测：无净值且无持仓 → 收益模块降级提示；成交缺 pnl 列且无法 FIFO 配平 → 交易模块降级；基准选中但无文件 → 基准子项省略。

## 接口映射

| 本 skill 概念 | 你的项目对应 |
|---|---|
| 策略净值 | `date, nav`（或 `ret`，自动 cumprod） |
| 基准净值 | `date, nav`（可选，缺则不硬算） |
| 成交记录 | `date, symbol, side, price, shares[, pnl][, commission]`（side: buy/sell） |
| 持仓市值 | `date, symbol, market_value`（或宽表 date×symbol） |
| 报告区间 | 频率选择 或 自定义起止日期 |

**判定基线**：年化 252 交易日、无风险利率默认 0、滚动 Sharpe 窗口 60、单边换手口径、风险样本下限 20 日。

## 按需加载

| 何时读 | 文件 |
|---|---|
| 全部公式 / 频率窗口 / 净值重建 / 对账规则 | `references/report-metrics.md` |
| 报告章节结构 / JSON schema / 输出契约 | `references/report-format.md` |
| 图表规格 / base64 机制 / 降级 | `references/visualization.md` |
| 数据来源与边界 / 降级规则 | `references/source_boundary.md` |

## QA 检查清单

- [ ] 口径（频率/基准/无风险利率/年化/窗口）是否在报告 0 节声明？
- [ ] 收益对账（日收益乘积 ≈ 区间收益 < 1e-6）是否通过？
- [ ] 净值来源是否标注（用户 NAV / 成交+持仓重建 / 降级）？
- [ ] 交易 PnL 口径（pnl 列 / FIFO 近似 / 降级）是否声明？
- [ ] HTML 是否自包含（离线打开、图片为 base64、无外链）？
- [ ] 四模块全覆盖（或 scope 明确收敛）？
- [ ] 结论是否 1-2 句，不堆数字？

## 跨工具适配

- OpenAI Codex / Assistants → `agents/openai.yaml`
- Cursor → `agents/cursor-rule.mdc`
- 无原生 skill 机制 → `agents/portable-loader.md`

---

## 项目边界（量化研究合规声明）

- **数据来源**：本 skill 不附带任何市场数据；净值/基准/成交/持仓由使用者提供（可经 pandadata 导出），数据合法性与许可由使用者负责。基准选项（000300.SH 等）仅为标签，skill 从不拉取指数数据。
- **假设与参数**：收益按几何年化（252 交易日）；无风险利率默认 0；由成交+持仓重建的净值为**近似**（假设持仓市值完整、现金变动全来自成交），报告中始终标注来源。
- **已知限制**：不自动拉取行情、不模拟实盘撮合；交易 PnL 在无 pnl 列且无法 FIFO 配平时降级；风险指标在样本 < 20 日时降级。
- **风险边界**：报告仅反映对给定材料 + 历史数据的统计归纳，不代表未来表现。
- **用途定位**：**仅供量化研究、教育与方法论参考**。不构成任何形式的投资建议、交易信号或获利保证。使用者据此实盘交易的全部后果由使用者自负。
