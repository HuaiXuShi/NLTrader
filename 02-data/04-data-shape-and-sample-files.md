# 数据形状与开发样本

## 目标

让不同模块消费的数据尽量稳定、统一。

## 推荐规范化后的 bars schema

```text
date: datetime
symbol: str
open: float | null
high: float | null
low: float | null
close: float | null
volume: float | null
amount: float | null
```

### 最低要求
如果第一版拿不到全部字段，至少保证：

- `date`
- `symbol`
- `close` 类字段
- `volume`

并在 provider 端映射成统一字段名。

Qlib 原始字段通常以 `$` 开头，例如 `$open`、`$close`。这些字段只允许出现在 `QlibDataProvider` 内部，传给 compiler / adapter / UI 前必须去掉 `$` 并统一列名。

## 推荐规范化后的 calendar schema

```text
date: datetime
is_open: bool
```

## 股票池文件格式

### 静态池 csv
```text
symbol
SH600036
SZ000001
SH600519
...
```

### 可选扩展字段
```text
symbol,name,weight
...
```

但第一版不依赖权重字段。

## sample_data 建议

```text
sample_data/
├── demo_symbols.csv
├── demo_pool_csi300_small.csv
├── nl_examples_single.md
└── nl_examples_cross_sectional.md
```

## 推荐开发样本

### 单股示例
建议至少包含：
- 银行股 1~2 只
- 白酒 / 消费 1~2 只
- 科技 / 制造 1~2 只

目的不是行业研究，而是让策略表现有差异，便于 UI 演示。

### 股票池示例
- 一个 20~50 只标的的静态池
- 尽量覆盖不同行业

### 时间跨度
- 近 3~5 年即可

## 统一 symbol 规范

第一版建议统一为：

- 上交所：`SHXXXXXX`
- 深交所：`SZXXXXXX`

UI 输入层可以接受但不能向下游传播：
- `sh600036`
- `600036`
- `600036.SH`

所有转换都在 `symbols.py` 完成，provider、DSL、compiler、Qlib adapter 均使用 Qlib 风格。
