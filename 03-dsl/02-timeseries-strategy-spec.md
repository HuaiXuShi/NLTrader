# 单股时序策略 DSL

## 适用场景

用于单只股票或少量指定股票的时间序列策略。

虽然 UI 第一版主要是单股输入，但 DSL 可以保留：
- `single_symbol`
- `symbol_list`

这样以后多股逐一回测不会改 schema。

## 最小结构示例

```json
{
  "strategy_kind": "timeseries",
  "market": "CN_A",
  "frequency": "D",
  "universe": {
    "type": "single_symbol",
    "symbols": ["SH600036"]
  },
  "rebalance": {
    "freq": "daily"
  },
  "signal": {
    "entry_rules": [],
    "exit_rules": []
  },
  "risk": {
    "stop_loss": 0.08,
    "take_profit": null,
    "max_holding_days": null
  },
  "execution": {
    "signal_time": "close",
    "execution_time": "next_open"
  }
}
```

## 支持的时序原语

### 指标
第一版建议支持：

- `SMA`
- `EMA`
- `RSI`
- `MACD`
- `BOLL_UPPER`
- `BOLL_LOWER`
- `RETURN_N`
- `VOL_MA_RATIO`

### 操作符
第一版建议支持：

- `>`
- `<`
- `>=`
- `<=`
- `cross_above`
- `cross_below`
- `breakout_high`
- `breakdown_low`

## Rule 结构建议

```json
{
  "lhs": {"indicator": "SMA", "params": [5]},
  "op": "cross_above",
  "rhs": {"indicator": "SMA", "params": [20]}
}
```

或者：

```json
{
  "lhs": {"indicator": "VOL_MA_RATIO", "params": [20]},
  "op": ">",
  "rhs": {"value": 1.5}
}
```

## 示例 1：均线金叉 + 放量确认

```json
{
  "strategy_kind": "timeseries",
  "universe": {"type": "single_symbol", "symbols": ["SH600036"]},
  "rebalance": {"freq": "daily"},
  "signal": {
    "entry_rules": [
      {
        "lhs": {"indicator": "SMA", "params": [5]},
        "op": "cross_above",
        "rhs": {"indicator": "SMA", "params": [20]}
      },
      {
        "lhs": {"indicator": "VOL_MA_RATIO", "params": [20]},
        "op": ">",
        "rhs": {"value": 1.5}
      }
    ],
    "exit_rules": [
      {
        "lhs": {"indicator": "CLOSE"},
        "op": "<",
        "rhs": {"indicator": "SMA", "params": [10]}
      }
    ]
  },
  "risk": {"stop_loss": 0.08},
  "execution": {"signal_time": "close", "execution_time": "next_open"}
}
```

## 目标权重语义

对单股时序策略，compiler 的语义应该非常简单：

- 满足持有条件 → `{symbol: 1.0}`
- 不满足持有条件 → `{}`

第一版不做复杂仓位管理时，这样最稳。

## 关于多条规则的逻辑

第一版建议默认：

- `entry_rules`：AND
- `exit_rules`：OR

如果未来扩展，再加入显式布尔组合。

## 时序策略第一版不建议做

- 同时多头多仓位梯度
- 加仓/减仓分层
- 盘中止损
- 任意布尔表达式树
- 跨标的联动条件
