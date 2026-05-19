# UI 状态与接口契约

## 推荐 UI 状态

### 全局状态
- `idle`
- `loading_parse`
- `loading_backtest`
- `success`
- `error`

### 每个 tab 可独立维护
避免一个 tab 的错误影响另一个 tab。

## 页面与核心模块的关系

UI 只做三件事：

1. 收集用户输入
2. 调 parser / Qlib evaluator 结果
3. 展示结果

UI 不应该：
- 自己计算指标
- 自己解释 DSL
- 自己直接调用 Qlib
- 自己处理大量数据清洗

## 推荐调用顺序

### 单股
1. 调用 parser，得到 `ParseResult`
2. 如果成功，调用 compiler + Qlib evaluator
3. 得到 `BacktestResult`
4. 渲染结果

### 横截面
1. 构造 universe spec
2. 调 parser
3. 再调用 compiler + Qlib evaluator
4. 渲染结果

## ParseResult 建议接口结构

```json
{
  "strategy_kind": "timeseries",
  "human_summary": "",
  "assumptions": [],
  "warnings": [],
  "parse_confidence": 0.82,
  "dsl": {}
}
```

## BacktestResult 建议接口结构

```json
{
  "strategy_summary": {},
  "capability_summary": {},
  "qlib_report": [],
  "qlib_positions": [],
  "qlib_analysis": {},
  "equity_curve": [],
  "positions_history": [],
  "trades": [],
  "rebalances": [],
  "metrics": {},
  "warnings": []
}
```

## UI 展示优先级建议

### 必须显示
- human_summary
- assumptions
- parse warnings
- metrics
- equity curve
- capability summary
- Qlib provider_uri / benchmark / evaluation config

### 推荐显示
- trades / rebalances

### 可后补
- 更多图表联动
- 下载功能
- DSL 原始 JSON 折叠展示

## 错误展示建议

把错误分成三类显示：

### 1. Parse error
例如：
- 当前策略超出支持范围
- 缺少股票池

### 2. Data error
例如：
- 股票代码不存在
- 某段数据缺失严重
- Qlib provider_uri 不存在或未初始化

### 3. Backtest error
例如：
- 编译失败
- 交易日历为空

保持错误文案简短且可执行，不要把 traceback 直接甩给用户。
