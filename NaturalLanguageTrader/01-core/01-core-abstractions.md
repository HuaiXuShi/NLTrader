# 核心抽象

## 总原则

这个项目必须通过少量高价值抽象来统一复杂度。  
最重要的不是“支持多少策略”，而是“所有策略最后如何落到同一个执行接口”。

## 抽象 1：DataProvider

职责：

- 提供价格与交易日历
- 提供股票池解析能力
- 暴露自身 capabilities
- 不把 Qlib 原生 API 暴露给上层

建议接口：

```python
class DataProvider:
    def get_capabilities(self) -> CapabilitySet: ...
    def get_calendar(self, start: str, end: str) -> CalendarFrame: ...
    def get_bars(
        self,
        symbols: list[str],
        start: str,
        end: str,
        adjusted_mode: str = "both",
    ) -> BarsFrame: ...
    def resolve_universe(
        self,
        universe_spec: UniverseSpec,
        start: str,
        end: str,
    ) -> list[str]: ...
    def get_limit_prices(...): ...
    def get_suspensions(...): ...
```

第一版默认实现是 `QlibDataProvider`。它内部可以调用 `qlib.data.D.calendar`、`D.instruments`、`D.list_instruments`、`D.features`，但上层只看到规范化后的 `CalendarFrame`、`BarsFrame` 和 universe 列表。

## 抽象 2：StrategyDSL

这是系统真正的“策略语言”，不是自然语言本身。

顶层字段建议：

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

说明：

- `timeseries` 策略主要依赖 `signal`
- `cross_sectional` 策略主要依赖 `selection + construction`
- 两者都可以使用 `risk` 和 `execution`

## 抽象 3：CompiledStrategy

这是 DSL 编译后的可执行对象。

最关键接口：

```python
class CompiledStrategy:
    def generate_target_weights(
        self,
        date: str,
        market_state: MarketState,
        portfolio_state: PortfolioState,
    ) -> dict[str, float]:
        ...
```

解释：

- 单股时序：  
  返回 `{symbol: 1.0}` 或 `{}`
- 横截面选股：  
  返回 `{symbol_a: 0.1, symbol_b: 0.1, ...}`

**这就是统一 Qlib 适配层的关键。** 这个接口和 Qlib `WeightStrategyBase.generate_target_weight_position(...)` 的语义接近，后者负责根据目标仓位生成订单。

## 抽象 4：BacktestResult

回测结果必须是结构化对象，而不是零散图表。

建议包含：

```python
@dataclass
class BacktestResult:
    strategy_summary: dict
    capability_summary: dict
    qlib_report: Any
    qlib_positions: Any
    qlib_analysis: dict
    equity_curve: Any
    positions_history: Any
    trades: Any
    rebalances: Any
    metrics: dict
    warnings: list[str]
```

## 抽象 5：ParseResult

建议单独建模，避免 parser 和 Qlib evaluator 紧耦合。

```python
@dataclass
class ParseResult:
    dsl: dict
    strategy_kind: str
    assumptions: list[str]
    warnings: list[str]
    human_summary: str
    parse_confidence: float
```

## 抽象 6：CapabilitySet

用来处理数据能力不完整的问题。

示例字段：

```python
{
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

## 为什么这几层是必须的

因为项目有两个天然复杂源：

1. 用户输入是不稳定的自然语言
2. 数据源能力不稳定

这两个不稳定性必须被挡在 DSL 和 CapabilitySet 之前。  
只有这样，引擎和 UI 才能保持确定性。

## Qlib 边界抽象

Qlib 相关能力建议封装为三个文件级抽象：

### `QlibDataProvider`
负责初始化和读取数据：
- `provider_uri`
- `region`
- calendar
- bars
- benchmark
- universe

### `QlibTargetWeightStrategy`
继承或包装 Qlib 的 target-weight 策略接口，只做一件事：
- 在每个交易日调用 `CompiledStrategy.generate_target_weights(...)`
- 把本项目 canonical weights 转成 Qlib target positions

### `QlibEvaluator`
负责运行 Qlib 回测并转换结果：
- 调用 Qlib `backtest` 或 `backtest_daily`
- 调用 `risk_analysis`
- 输出 `BacktestResult`

这样 parser、compiler、UI 都不需要知道 Qlib 内部对象。
