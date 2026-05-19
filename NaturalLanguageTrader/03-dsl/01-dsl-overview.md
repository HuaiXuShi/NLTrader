# DSL 总体设计

## 设计目标

DSL 不是为了“完美表达所有策略”，而是为了：

1. 把自然语言压缩为可执行结构
2. 让 parser、compiler、Qlib adapter 分层
3. 让系统支持时序和横截面两类策略
4. 让 assumptions 和 warnings 可显式展示

## 顶层结构建议

```json
{
  "strategy_kind": "timeseries | cross_sectional",
  "market": "CN_A",
  "frequency": "D",
  "universe": {},
  "rebalance": {},
  "signal": {},
  "selection": {},
  "construction": {},
  "risk": {},
  "execution": {},
  "assumptions": [],
  "warnings": [],
  "parse_confidence": 0.0
}
```

## 字段说明

### `strategy_kind`
必须值：
- `timeseries`
- `cross_sectional`

### `universe`
定义策略作用对象。

内部 symbol 使用 Qlib 风格：
- `SH600036`
- `SZ000001`

UI 可以兼容其他输入格式，但进入 DSL 前必须完成标准化。

### `rebalance`
定义调仓频率：
- `daily`
- `weekly`
- `monthly`

### `signal`
主要用于时序策略，表达买入/卖出条件。

### `selection`
主要用于横截面策略，表达：
- 过滤
- 打分
- 排序
- top/bottom N

### `construction`
主要用于组合构建：
- 等权
- 最大持仓数
- 权重约束（第一版可简化）

### `risk`
通用风控：
- 止损
- 止盈
- 最大持有天数

### `execution`
统一执行模型参数：
- `signal_time = close`
- `execution_time = next_open`

## 一个重要约束

不是每个字段都在每类策略中生效。

### 对时序策略
重点字段：
- `universe`
- `signal`
- `risk`
- `execution`

### 对横截面策略
重点字段：
- `universe`
- `rebalance`
- `selection`
- `construction`
- `risk`
- `execution`

## 为什么不用“策略模板大全”

因为那样会越来越重。  
DSL 的价值在于：

- 支持少量原语
- 通过组合表达很多策略
- 后续扩一个原语就能扩很多策略

## 统一执行语义

无论是哪类策略，最终都必须被 compiler 转成：

> 给定一个日期，返回一组目标权重

这就是把复杂语义统一到底层引擎的核心。
