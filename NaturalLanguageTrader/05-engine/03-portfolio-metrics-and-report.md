# 组合、指标与报告

## BacktestResult 建议结构

```python
{
  "strategy_summary": {},
  "capability_summary": {},
  "qlib_report": ...,
  "qlib_positions": ...,
  "qlib_analysis": {},
  "equity_curve": ...,
  "positions_history": ...,
  "trades": ...,
  "rebalances": ...,
  "metrics": {},
  "warnings": []
}
```

## strategy_summary 建议内容

- strategy_kind
- universe_summary
- rebalance_summary
- human_summary
- assumptions
- parse_warnings

## metrics 建议的最小集合

### 必备
- total_return
- annualized_return
- max_drawdown
- information_ratio 或 sharpe（二者至少一个）
- num_trades

### 推荐
- win_rate
- avg_holding_days
- turnover
- benchmark_return（若有基准）

第一版指标以 Qlib `risk_analysis` 为主，不重复实现复杂风险分解。

## trades 建议字段

| 字段 | 说明 |
|---|---|
| `date` | 成交日或 Qlib 交易日 |
| `symbol` | 股票代码 |
| `side` | buy / sell |
| `price` | 成交价 |
| `shares` | 成交股数 |
| `gross_amount` | 成交金额 |
| `fees` | 手续费合计 |
| `reason` | 触发原因摘要 |

## rebalances 建议字段

| 字段 | 说明 |
|---|---|
| `date` | 调仓日 |
| `selected_symbols` | 当次入选股票 |
| `target_weights` | 目标权重 |
| `notes` | 调仓说明 |

## positions_history 建议字段

- date
- symbol
- shares
- market_value
- weight

## 页面图表建议

### 单股
- 价格图 + 买卖点
- 净值曲线

### 横截面
- 净值曲线
- 持仓数量变化
- 调仓记录表
- benchmark / excess return（若 Qlib report 中可用）

## 解释能力建议

报告至少要能解释三类事情：

### 1. 系统如何理解策略
来自 parser：
- strategy_kind
- assumptions
- warnings

### 2. 系统如何执行回测
来自 capability summary：
- 哪些规则启用了
- 哪些规则没启用
- 降级原因
- Qlib `provider_uri`、`benchmark`、`exchange_kwargs`

### 3. 系统在关键时点做了什么
来自 trades / rebalances：
- 为什么买
- 为什么卖
- 为什么调仓

第一版不需要对每一笔交易都做超详细叙述，但至少要能把原因摘要保留下来。
