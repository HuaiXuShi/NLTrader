# NLTrader Streamlit UI

NLTrader 是自然语言驱动的量化策略解析与回测前端。当前版本采用浅色金融研究平台风格，主界面聚焦策略输入、结构化解析和回测报告，不在主流程暴露开发状态。

## 环境与启动

要求 Python >= 3.10。依赖版本下限：

```text
streamlit>=1.32
pandas>=2.0
numpy>=1.24
plotly>=5.18
```

安装依赖：

```bash
pip install -r requirements.txt
```

启动页面：

```bash
streamlit run app/streamlit_app.py
```

## 当前 UI 结构

页面保留两个主 tab：

- `单股时序策略`
- `股票池横截面策略`

每条路径都按同一主线组织：

1. **顶部 Hero**：只展示 NLTrader、产品说明和支持能力。
2. **自然语言策略**：输入完整中文策略，并配置股票代码、日期、初始资金或股票池。
3. **两阶段操作**：`解析策略` 只调用 `parse_strategy(...)`；`运行回测` 只调用 `run_backtest(...)`。
4. **策略解析报告**：只展示结构化策略摘要，不展示解析置信度或解析轨迹。
5. **回测报告**：展示策略概览、核心指标、交易视图、净值曲线、回撤分析和记录表。
6. **底部折叠信息**：解析后只保留 `查看策略 DSL`，用于查看结构化策略 JSON。

## 视觉方向

本轮 UI 参考了 Composer、QuantConnect、TradingView、Koyfin 的公开网页和产品界面展示：

- Composer 的自然语言策略创建和策略规则组织。
- QuantConnect 的回测结果层级，包括 equity curve、trades、statistics、drawdown。
- TradingView 的图表优先、区间切换、指标线、成交量和交易标记。
- Koyfin 的浅色金融分析平台观感、指标卡和报表布局。

NLTrader 没有接入这些产品的服务、widget 或数据源，只借鉴信息层级和视觉方向。

## 后端与接口说明

Streamlit 主页面只从 adapter 导入两个函数：

```python
from app.backend_adapter import parse_strategy, run_backtest
```

接口契约保持不变：

```python
parse_strategy(strategy_text, strategy_kind, context=None)
run_backtest(parse_result, config)
```

当前 `app/backend_adapter.py` 转发到 `app.mock_backend`。后续接入真实 LLM parser 或 Qlib evaluator 时，应保持函数签名和返回字段兼容，避免重写主流程 UI。

## ParseResult 契约

UI 期望 `parse_strategy(...)` 返回一个 dict，关键字段如下：

```python
{
    "strategy_kind": "timeseries | cross_sectional",
    "human_summary": "...",
    "assumptions": ["..."],
    "warnings": ["..."],
    "parse_confidence": 0.88,
    "dsl": {}
}
```

字段说明：

- `strategy_kind`：策略类型。
- `human_summary`：自然语言解析摘要。
- `assumptions`：parser 自动补充的默认假设。
- `warnings`：mock、歧义、能力边界或降级说明。
- `parse_confidence`：0 到 1 的解析置信度；主界面不展示，仅作为接口字段保留。
- `dsl`：受控 DSL JSON；主界面底部通过 `查看策略 DSL` 展开查看。

## BacktestResult 契约

UI 期望 `run_backtest(...)` 返回一个 dict，关键字段如下：

```python
{
    "strategy_summary": {},
    "capability_summary": {},
    "equity_curve": [],
    "benchmark_curve": [],
    "price_data": [],
    "trades": [],
    "rebalances": [],
    "positions_history": [],
    "metrics": {},
    "warnings": []
}
```

常用字段：

- `strategy_summary`
  - 单股：`strategy_kind`、`symbol`、`date_range`、`completed_round_trips`
  - 横截面：`strategy_kind`、`universe_size`、`top_n`、`date_range`、`rebalance_freq`
- `metrics`
  - `total_return`、`annualized_return`、`max_drawdown`、`sharpe`
  - 其他指标可保留，但主界面只突出核心四项。
- `price_data`
  - 单股图表支持 `open/high/low/close`、`sma5`、`sma10`、`sma20`、`volume`、`volume_ma20`
- `trades`
  - `date`、`symbol`、`side`、`price`、`quantity`、`weight`、`reason`
- `rebalances`
  - `date`、`selected_symbols`、`avg_weight`、`turnover`、`reason`
- `positions_history`
  - `date`、`symbol`、`weight`、`score`、`rank`
- `capability_summary`
  - 作为后端能力说明字段保留，主界面不展示。

更完整的类型说明见 `app/contracts.py`。

## 默认策略

单股时序策略：

```text
5日均线上穿20日均线且成交量大于20日均量1.5倍时买入，跌破10日均线或亏损8%卖出
```

股票池横截面策略：

```text
每月调仓，在股票池中选择过去20日涨幅最高的10只股票等权持有
```

本地 mock backend 会生成可复现的 OHLCV、交易记录、组合调仓、净值曲线、benchmark 曲线和指标。主界面不展示 mock/backend/pending 等开发状态，这些说明只保留在 README 中。

## Troubleshooting

如果系统提示找不到 `streamlit` 命令，请先安装依赖：

```bash
pip install -r requirements.txt
```

如果出现 `import app` 失败，请确认在项目根目录运行：

```bash
streamlit run app/streamlit_app.py
```

当前版本不需要 API key、不需要安装 Qlib、不需要准备 Qlib 数据目录，也不需要联网。
