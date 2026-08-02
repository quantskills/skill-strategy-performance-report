# 可视化规格与机制

> 本 skill 是生态首个带可视化（且交互式）的 skill。机制：手写 **ECharts option（纯 JSON）** → 运行时 `echarts.min.js`（Apache-2.0，vendored）内嵌进自包含 HTML → 浏览器交互渲染。离线可用、单文件、无外链。

## 图表清单

| 键 | 标题 | 数据源 | 形式 |
|---|---|---|---|
| `equity_curve` | 净值 vs 基准（归一化 1.0） | `returns.series.nav` / `bench_norm` | 折线（蓝=策略 橙=基准）+ dataZoom 缩放 |
| `drawdown` | 回撤（%） | `risk.series.drawdown` | 面积（红）+ 零参考线 |
| `monthly_returns` | 月度收益热图（%） | `nav.pct_change()` 按年×月分组 | heatmap（蓝=负→灰=0→红=正）+ visualMap |
| `rolling_sharpe` | 滚动 Sharpe | `risk.series.rolling_sharpe` | 折线 + 零参考线 |
| `trade_pnl` | 交易 PnL 分布 | `trades.data.pnl_list`（np.histogram 分箱） | 柱状（红=盈利 蓝=亏损） |
| `period_returns` | 分桶区间收益（%） | `returns.data.period_over_period` | 柱状（红=正 蓝=负） |
| `concentration` | Top-N 持仓权重（%） | `positions.data.current_holdings` | 横向柱状（蓝） |

无数据/模块降级时对应图自动跳过。所有图支持悬停 tooltip、图例开关、dataZoom（折线）。

## 设计约定（对齐 dataviz 方法论，颜色来自验证过的参考调色板）

- **类别色按固定顺序分配，从不循环**：策略=蓝 `#2a78d6`、基准=橙 `#eb6834`；第 3 个及以上系列并入 Other / 小多图，绝不临时生成色相。
- **分叉（极性）蓝↔红 + 中性灰 `#f0efec` 中点**：A 股习惯红=涨/正收益，蓝=跌/负收益。热图与正负柱状用此对。
- **单一 y 轴**：净值/基准均归一化到 1.0，绝不用双 y 轴。
- **文字用墨色**：坐标轴刻度 `#898781`、图例默认，绝不用系列色承载文字身份。
- **图表面 `#fcfcfb`**，网格弱化。

## 技术机制

- **option 为纯 JSON**：`charts.py` 手写 ECharts option dict，只含 list/str/float/bool/None（数值经 `float()`/`round()` 转换、NaN→`None`）。`build_charts()` 永不因缺库失败。
- **运行时 vendored**：`assets/echarts.min.js`（Apache-2.0，~1MB）随 skill 分发，`html_report.py` 构建时读入并内嵌进单文件 HTML（`<script>…echarts.min.js…</script>`）。离线断网可看全部交互图。
- **CDN 回退**：若 `assets/echarts.min.js` 缺失（异常情况），`html_report.py` 回退内联 `<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js">`（此时看图需联网）。
- **初始化脚本**：每图一个 `<div id="chart_<key>" style="height:380px">`，结尾单个 `<script>` 里 `echarts.init(document.getElementById('chart_<key>')).setOption(<json>)`；options 经 `json.dumps(ensure_ascii=False)` 内嵌，并转义 `</` 防止闭合 script。
- **降级**：charts 为空（异常）→ 表格型 HTML + 横幅「（图表运行时不可用，已降级为表格）」，绝不出现坏图。

## 换用其他 JS 图表库（可选增强）

要换成 Plotly / lightweight-charts 等：仅需改 `charts.py`（把 option dict 换成目标库配置）与 `html_report.py`（运行时脚本 + 容器）。数据流与表格不变。默认实现保持 ECharts（中国量化事实标准）。
