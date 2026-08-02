# 绩效指标公式与口径（心脏文档）

> 本 skill 的全部公式、频率窗口定义、净值重建规则与对账规则。判定基线：年化 252 交易日、无风险利率默认 0、滚动 Sharpe 窗口 60、单边换手口径、风险样本下限 20 日。

## 一、频率窗口定义

| 频率 | 报告窗口 | 分桶粒度 |
|---|---|---|
| `daily` | 最后一个交易日 | 每日 |
| `weekly` | 最后一个 ISO 周（周一~周五） | ISO 周 |
| `monthly` | 最后一个自然月 | 自然月 |
| `semi_annual` | 最后 126 个交易日 | 自然月 |
| `annual` | 最后 252 个交易日 | 自然月 |
| `custom` | `[start, end]`；缺起止 → 退化为最近一个月（报告中标注） | 每日 |

窗口取「净值序列中实际存在的日期」，不臆测缺失日。

## 二、收益指标

设区间起点净值 `NAV_s`、终点 `NAV_e`，日收益 `r_t = NAV_t / NAV_{t-1} − 1`：

- **区间收益** `r_p = NAV_e / NAV_s − 1`
- **累计收益** `r_cum = NAV_last / NAV_first − 1`（自策略起点）
- **年化收益**（几何，年化 N=252 交易日）
  `r_ann = (1 + r_cum)^(N / T_days) − 1`，`T_days = max(末日期 − 首日期天数, 1)`；`1 + r_cum ≤ 0` 时返回 `None`
- **分桶收益**：按分桶粒度分组，桶内 `prod(1 + r_t) − 1`
- **超额收益**（有基准时）：
  - 算术超额 `= r_p − r_b`
  - 相对超额 `= (1 + r_p) / (1 + r_b) − 1`
  - 超额曲线 `= NAV_norm / B_norm`（两者均归一到 1.0）

**基准处理**：基准选项（000300.SH 等）只是标签；skill 从不拉取指数数据。选中基准但无基准文件 → 基准子项省略并在报告中注明，绝不编造指数收益。

## 三、风险指标

- **最大回撤** `MDD = min_t(NAV_t / max_{u≤t} NAV_u − 1)`；记录 `mdd_start`（回撤起点 = 峰值日）、`mdd_end`（谷值日）、`mdd_recovery`（谷后首个收复峰值的日期，未修复则为 `None`）
- **年化波动率** `σ_ann = std(r_t) × √N`（ddof=1）
- **Sharpe** `(mean(r_t) − rf/N) / std(r_t) × √N`
- **Sortino** `(mean(r_t) − rf/N) / σ_downside × √N`，`σ_downside = std(r_t | r_t < 0)`
- **Calmar** `r_ann / |MDD|`；`MDD ≥ 0` 或 `r_ann = None` 时返回 `None`
- **滚动 Sharpe**：`rolling_sharpe_window`（默认 60）日滚动 Sharpe
- **最优/最差日**：区间内 `r_t` 最大/最小的日期与收益
- **样本守卫**：日收益样本 < `min_sample_days`（默认 20）→ 风险模块整体降级「样本不足」（日报/周报样本天然不足，属设计行为）

## 四、交易指标（PnL 口径优先级）

1. **`pnl` 列**：直接用成交表携带的 PnL → `pnl_source = "pnl_column"`
2. **FIFO 配平**：无 `pnl` 列时，按 `symbol` 分组、时间顺序买入/卖出配对，卖出以先进先出成本结算已实现盈亏（扣佣金）→ `pnl_source = "fifo_mark_to_market"`；某标卖出量超过已买入量（无法配平）→ 整体降级
3. **无法配平** → `pnl_source = "none"`，交易模块降级提示，绝不臆测

- 胜率 `= 盈利笔数 / 平仓笔数`（平仓 = PnL≠0）
- 盈亏比 `= 毛盈利 / 毛亏损`（`毛亏损` 取正；除零 → `None`）
- 平均盈利 / 平均亏损、按分桶 PnL、按标的 PnL、PnL 分布序列
- **平均持仓天数**（仅 FIFO 口径可得）：`Σ 营业日近似 / 笔数`，营业日近似 = 自然日 × 5/7
- 样本守卫：平仓笔数 < 3 → 交易模块降级「样本过少」

## 五、净值重建规则（无 NAV 时）

优先级：

1. **用户 NAV** → `nav_source = "user_nav"`（权威，直接用）
2. **有持仓** → 现金法：
   `cash_0 = (1 − MV_0)`（缺省初始现金）或 `(initial_cash − MV_0)`；`cash_t = cash_0 + Σ_{u≤t}(卖出所得 − 买入成本 − 佣金)`；`equity_t = MV_t + cash_t`；`NAV = equity / equity_0` → `nav_source = "reconstructed_cash"`（标注「近似」）
3. **有持仓无成交** → 满仓法：`NAV = MV / MV_0` → `nav_source = "reconstructed_mv"`
4. **两者皆无** → `None` + 降级提示

重建的净值是**近似**：假设持仓市值完整、现金变动全来自成交；缺省锚定 `equity_0 = 1.0`（展示收益表现，非绝对 PnL）。`--initial-cash` 可选开启绝对口径。报告口径声明中始终标注 `nav_source`。

## 六、持仓与换手

- **当前持仓**：最新日各标的市值与权重
- **Top-N 集中度**：最新日前 N 大权重之和（N = `top_n`，默认 10）
- **单边换手** `OT_t = Σ_s |w_s,t − w_s,t−1|`，`one_way_turnover = mean_t(OT_t) / 2`（需要 ≥ 2 个持仓日期）
- **本期调仓次数** = 窗口内成交日数（需成交数据；无成交 → 该子项省略并注明）

## 七、对账规则

- **收益对账**：窗口内 `prod(1 + r_t)` 与 `1 + r_p` 的残差须 < `1e-6`，对不上就是 bug
- **累计对账**：全序列 `prod(1 + r_t)` 与 `1 + r_cum` 残差
- JSON `reconciled` 字段 = returns 模块 `recon_residual < 1e-6`

## 八、图表公式映射

| 图 | 数据 |
|---|---|
| 净值 vs 基准 | `NAV / NAV_0`、`B / B_0` |
| 回撤 | `NAV / cummax(NAV) − 1` |
| 月度收益热图 | 按年×月分组的 `prod(1 + r_t) − 1` |
| 滚动 Sharpe | 60 日滚动年化 Sharpe |
| 交易 PnL 分布 | `pnl_list`（非零部分） |
| 分桶区间收益 | `period_over_period` |
| 集中度 | Top-N 持仓权重 |
