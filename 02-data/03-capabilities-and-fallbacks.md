# 数据能力标记与降级逻辑

## 为什么必须有 capability layer

当前数据源并不保证总能提供以下信息：

- 停牌
- 涨跌停价
- 动态指数成分股
- 原始价 / 复权价双序列

如果没有能力声明，系统会出现两种坏结果：

1. 假装支持，实际不准确
2. 到处写 if-else，系统越来越乱

所以必须统一为：

> provider 声明能力，Qlib adapter / evaluator 按能力启用规则，report 把能力摘要显示给用户。

## 推荐 capability flags

```json
{
  "has_calendar": true,
  "has_ohlcv": true,
  "has_adjusted_prices": true,
  "has_raw_prices": false,
  "has_suspend_info": false,
  "has_limit_prices": false,
  "has_limit_threshold": true,
  "has_dynamic_universe_membership": true,
  "has_benchmark_series": true,
  "uses_qlib_region_cn": true
}
```

## 降级规则建议

### 1. 没有停牌信息
- 不启用“停牌导致无法成交”的真实约束
- 执行模型退化为“只要有下一交易日价格即可交易”
- 在结果中记录 warning

### 2. 没有涨跌停价
- 不启用“涨跌停导致无法成交”的约束
- 在 capability summary 里明确显示

### 3. 没有 raw / adjusted 双序列
- 用唯一可得序列同时做信号和成交
- 明确输出 warning：`price_mode_degraded`

### 4. 没有动态股票池成分历史
- 横截面策略只允许：
  - 静态预置池
  - 用户自定义股票列表
- 不支持历史动态成分精确还原

### 5. 没有基准指数序列
- 不展示 benchmark 曲线
- 结果页提示 `benchmark_unavailable`

## Qlib 版 capability summary 建议进入每次回测结果

例如：

```json
{
  "provider_name": "QlibDataProvider",
  "provider_uri": "~/.qlib/qlib_data/cn_data",
  "region": "cn",
  "benchmark": "SH000300",
  "effective_rules": [
    "qlib_daily_executor",
    "transaction_costs",
    "trade_unit_100",
    "limit_threshold_0.095"
  ],
  "disabled_rules": [
    "minute_level_execution",
    "live_trading"
  ],
  "data_warnings": [
    "demo_data_may_be_imperfect"
  ]
}
```

## UI 展示建议

页面上单独展示一张说明卡片：

- 数据源与 provider_uri
- 当前启用规则
- 当前未启用规则
- 降级原因

这样做能让答辩时的风险大幅下降，因为你没有“伪装成精确市场还原”。
