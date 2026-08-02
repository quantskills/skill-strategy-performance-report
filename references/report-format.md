# 绩效报告输出格式

> 报告是交付物。固定结构，让不同频率/不同策略之间的报告可比。HTML 为主（自包含、图表内嵌），Markdown + JSON 供程序消费。

## 报告结构

```markdown
# A股策略绩效报告
> 生成：{ts}　策略：{name}　频率：{freq}　基准：{benchmark}

## 0. 口径声明        # 区间 / 净值来源 / 无风险利率 / 年化 / PnL 口径 / 退化说明
## 1. 收益            # 区间/累计/年化 + 分桶表 + 基准对比 + 对账
## 2. 风险            # MDD / 波动 / Sharpe / Sortino / Calmar / 滚动 / 最优最差日
## 3. 交易分析        # PnL 口径 / 胜率 / 盈亏比 / 分布（按桶/按标的）/ 持仓天数
## 4. 持仓与换手      # 当前持仓表 / 集中度 / 单边换手 / 调仓次数
## 图表               # 7 张交互式 ECharts 图（位于 HTML；Markdown 仅一行指引到 strategy_report.html）
## 5. 结论            # 1-2 句，不堆数字
## 6. 合规声明
```

HTML 与 Markdown 共享同一份 `PerfResult.data`，并由 `report-format.md` 固定章节顺序，二者不会漂移。

## scripts 输出契约

`strategy_report_cli.py --out out/` 产出：

- `out/strategy_report.md` — Markdown 报告（图表区为指引行，指向 HTML）
- `out/strategy_report.json` — 机器可读（schema 见下）
- `out/strategy_report.html` — 自包含 HTML 仪表盘（交互式 ECharts 内嵌，`output_format` 为 `all`/`html` 时）

JSON schema：`"schema": "skill-strategy-performance-report/1"`

```json
{
  "schema": "skill-strategy-performance-report/1",
  "generated_at": "YYYY-MM-DD",
  "meta": { "strategy_name", "frequency", "benchmark", "risk_free_rate",
            "annualization", "rolling_sharpe_window", "nav_source" },
  "modules": { "returns": {...}, "risk": {...}, "trades": {...}, "positions": {...} },
  "charts": [ { "key": "equity_curve", "title": "..." }, ... ],
  "reconciled": true
}
```

每个模块对象：`{ "name", "data", "recon_residual", "degraded", "note" }`。`charts` 仅带键引用（base64 体积大，图表本体在 HTML / Markdown 中）。

## 写作纪律

1. **口径先行**：频率、基准、无风险利率、年化、窗口、净值来源、PnL 口径在 0 节声明。
2. **对账必附**：收益对账残差在 1 节给出，< 1e-6 标注「通过」。
3. **降级必标**：模块 `degraded` 时用 `（降级：{note}）` 明示，绝不装作数据齐全。
4. **分层结论**：结论 1-2 句（收益、超额方向、回撤、胜率），不堆数字。
5. **合规兜底**：所有报告以合规声明收尾。
