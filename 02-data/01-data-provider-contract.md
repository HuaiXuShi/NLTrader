# DataProvider 契约

## 目标

业务层不应该知道数据来自哪里。  
它只应该知道：

- 能取到哪些数据
- 数据长什么样
- 数据能力是否完整

Qlib 版第一实现是 `QlibDataProvider`，但 parser / compiler / UI 不应该直接调用 `qlib.data.D`。

## 必需接口

### 1. `get_capabilities()`
返回能力声明，用于控制 Qlib adapter / evaluator 是否启用某些规则。

```python
CapabilitySet = {
    "has_calendar": True,
    "has_ohlcv": True,
    "has_adjusted_prices": True,
    "has_raw_prices": False,
    "has_suspend_info": False,
    "has_limit_prices": False,
    "has_limit_threshold": True,
    "has_dynamic_universe_membership": True,
    "has_benchmark_series": True,
    "uses_qlib_region_cn": True
}
```

### 2. `get_calendar(start, end)`
返回交易日列表。  
这是 Qlib adapter 推进日频回测的基础。

### 3. `get_bars(symbols, start, end, fields=None)`
返回统一格式的日线数据。

`fields` 默认：
- `$open`
- `$high`
- `$low`
- `$close`
- `$volume`

### 4. `resolve_universe(universe_spec, start, end)`
根据 DSL 中的 universe 定义，解析出实际股票列表。

支持的最小 universe 类型：

- `single_symbol`
- `symbol_list`
- `preset_pool`（映射到 Qlib market，如 `csi300`）
- `uploaded_pool`（可作为 UI 层输入后转成 symbol_list）

### 5. 可选接口
这些接口是“有更好，没有就降级”。

- `get_limit_prices(...)`
- `get_suspensions(...)`
- `get_constituent_history(...)`

## BarsFrame 最小字段

建议规范化后至少包含：

| 字段 | 说明 |
|---|---|
| `date` | 交易日 |
| `symbol` | 股票代码 |
| `open` | 开盘价 |
| `high` | 最高价 |
| `low` | 最低价 |
| `close` | 收盘价 |
| `volume` | 成交量 |
| `amount` | 成交额，可选 |

如果后续要区分 raw / adjusted 双序列，再扩展 `open_raw`、`open_adj` 等字段；V1 不强制要求。

Qlib 默认 `D.features` 字段建议先取：

```python
["$open", "$high", "$low", "$close", "$volume"]
```

Provider 再映射为本项目字段。

## CalendarFrame 最小字段

- `date`
- `is_open`

## UniverseSpec 最小结构

```json
{
  "type": "single_symbol | symbol_list | preset_pool",
  "symbols": [],
  "pool_name": null,
  "qlib_market": null
}
```

示例：

```json
{"type": "preset_pool", "pool_name": "CSI300", "qlib_market": "csi300"}
```

## Provider 的边界

### Provider 负责
- 拉数据
- 清洗列名
- 统一 symbol 格式
- 初始化 Qlib
- 解析 Qlib market / instruments
- 声明 provider_uri、region、benchmark

### Provider 不负责
- 指标计算
- 策略逻辑
- 权重构建
- 成本计算
- UI 展示
- 直接决定 Qlib 回测参数
