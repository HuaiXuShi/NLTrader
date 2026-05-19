# 横截面选股策略 DSL

## 适用场景

用于股票池内部的筛选、排序和组合构建。

## 最小结构示例

```json
{
  "strategy_kind": "cross_sectional",
  "market": "CN_A",
  "frequency": "D",
  "universe": {
    "type": "preset_pool",
    "pool_name": "demo_pool"
  },
  "rebalance": {
    "freq": "monthly"
  },
  "selection": {
    "filters": [],
    "score": {},
    "rank_order": "desc",
    "top_n": 10
  },
  "construction": {
    "weighting": "equal_weight"
  },
  "risk": {},
  "execution": {
    "signal_time": "close",
    "execution_time": "next_open"
  }
}
```

## 选择逻辑拆解

横截面策略建议固定成 5 步：

1. resolve universe
2. apply filters
3. compute score
4. rank
5. select + construct weights

这 5 步比“自由表达的复杂选股公式”更适合第一版。

## 支持的横截面原语

### filters
例如：
- 20 日均成交量大于阈值
- 股价高于某条均线
- RSI 小于某阈值

### score
第一版建议只支持单一主因子打分：
- `RETURN_N`
- `RSI`
- `SMA_GAP`
- `VOL_MA_RATIO`

以后再扩多因子组合。

### rank_order
- `asc`
- `desc`

### select
- `top_n`
- `bottom_n`

### construction
第一版建议只做：
- `equal_weight`

## 示例：月度动量 top 10

```json
{
  "strategy_kind": "cross_sectional",
  "market": "CN_A",
  "frequency": "D",
  "universe": {
    "type": "symbol_list",
    "symbols": ["SH600036", "SH600519", "SZ000001", "SZ000858"]
  },
  "rebalance": {
    "freq": "monthly"
  },
  "selection": {
    "filters": [],
    "score": {
      "factor": "RETURN_N",
      "params": [20]
    },
    "rank_order": "desc",
    "top_n": 2
  },
  "construction": {
    "weighting": "equal_weight"
  },
  "risk": {},
  "execution": {
    "signal_time": "close",
    "execution_time": "next_open"
  }
}
```

## 目标权重语义

例如选出 2 只：

```json
{
  "SH600036": 0.5,
  "SH600519": 0.5
}
```

如果筛选后不足 N 只，第一版建议：
- 对剩余股票等权
- 同时记录 warning

## 横截面第一版明确不做

- 全市场实时扫描
- 历史动态指数成分精确还原
- 多因子优化器
- 风格中性约束
- 行业约束
- 风险预算
- 卖空
