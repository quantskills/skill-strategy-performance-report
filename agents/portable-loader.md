# Portable Loader（无原生 skill 机制的平台）

在 OpenAI Assistants / Codex / Cursor / OpenClaw 等未原生支持本 skill 元数据的平台上，直接加载以下内容即可获得同等能力：

1. **读取 `SKILL.md`**：核心协议（四模块、标准 8 步工作流、对账纪律、合规声明）。这是行为契约，必须完整加载。
2. **按需加载 `references/`**：
   - `report-metrics.md` — 全部公式 / 频率窗口定义 / 净值重建规则 / 对账规则（心脏文档）
   - `report-format.md` — 报告输出契约
   - `visualization.md` — 图表规格与 base64 机制
   - `source_boundary.md` — 数据来源与边界
3. **可选运行 `scripts/`**：`strategy_report_cli.py` 生成报告；`self_test.py` 跑通自检（含对账/重建/降级断言）。依赖 pandas + numpy（见 `scripts/requirements.txt`）；图表为 ECharts 交互图，运行时 `assets/echarts.min.js` 随 skill 内嵌分发（缺失时自动回退 CDN）。

## 最小加载清单

```
SKILL.md
references/report-metrics.md
references/report-format.md
```

其余 references 在对应模块被触发时再读取。
