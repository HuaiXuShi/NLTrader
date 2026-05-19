# Qlib 策略适配与评测映射

## 目标

这一层把本项目的自然语言策略结果接入 Qlib，而不是重写一个完整撮合引擎。

核心链路：

```text
ParseResult
  ↓
StrategyDSL
  ↓
CompiledStrategy.generate_target_weights(...)
  ↓
QlibTargetWeightStrategy
  ↓
Qlib backtest / backtest_daily
  ↓
risk_analysis
  ↓
BacktestResult
```

## 推荐实现文件

- `src/qlib_strategy_adapter.py`
- `src/qlib_evaluator.py`
- `src/report.py`

## QlibTargetWeightStrategy

Qlib 提供 target-weight 风格的策略基类。它关注目标持仓比例，并能根据目标仓位生成订单。

本项目 adapter 的职责：

1. 持有 `CompiledStrategy`。
2. 在每个 Qlib 交易日构建 `MarketState`。
3. 调用 `generate_target_weights(date, market_state, portfolio_state)`。
4. 检查 long-only、权重和不超过 1。
5. 返回 Qlib 需要的 target position。

伪代码：

```python
class QlibTargetWeightStrategy(WeightStrategyBase):
    def __init__(self, compiled_strategy, data_provider, execution_config):
        self.compiled_strategy = compiled_strategy
        self.data_provider = data_provider
        self.execution_config = execution_config

    def generate_target_weight_position(self, *args, **kwargs):
        date = self._resolve_current_date(*args, **kwargs)
        market_state = self.data_provider.build_market_state(date)
        portfolio_state = self._build_portfolio_state()
        weights = self.compiled_strategy.generate_target_weights(
            date=date,
            market_state=market_state,
            portfolio_state=portfolio_state,
        )
        return self._validate_and_normalize(weights)
```

具体函数签名以安装的 Qlib 版本为准，文档中只锁定职责边界。

## QlibEvaluator

Evaluator 负责统一配置并调用 Qlib 回测。

推荐默认配置：

```python
backtest_config = {
    "start_time": start,
    "end_time": end,
    "account": 100000000,
    "benchmark": "SH000300",
    "exchange_kwargs": {
        "freq": "day",
        "limit_threshold": 0.095,
        "deal_price": "close",
        "open_cost": 0.0005,
        "close_cost": 0.0015,
        "min_cost": 5,
    },
}
```

说明：
- `deal_price="close"` 先与 Qlib 示例保持一致，便于确认主链路。
- 如果要展示“收盘信号、次日开盘成交”，需要在 adapter 层做信号日期滞后，并把 `deal_price` 改为可验证的成交字段。
- 所有配置必须进入 `capability_summary`，不能只藏在代码里。

## 结果映射

Qlib 常见输出：

- `report_normal`
- `positions_normal`
- `risk_analysis(...)`

映射到本项目：

| Qlib 输出 | BacktestResult 字段 | 说明 |
|---|---|---|
| `report_normal["return"]` | `equity_curve` | 策略收益序列，可累计成净值 |
| `report_normal["bench"]` | `benchmark_curve` | 基准收益序列 |
| `report_normal["cost"]` | `cost_curve` | 交易成本 |
| `report_normal["turnover"]` | `metrics.turnover` | 换手 |
| `positions_normal` | `positions_history` | 持仓记录 |
| `risk_analysis` | `metrics` / `qlib_analysis` | mean、std、annualized_return、information_ratio、max_drawdown |

## 必须保留的解释字段

`BacktestResult.capability_summary` 至少包含：

```json
{
  "provider_name": "QlibDataProvider",
  "provider_uri": "~/.qlib/qlib_data/cn_data",
  "region": "cn",
  "benchmark": "SH000300",
  "deal_price": "close",
  "limit_threshold": 0.095,
  "open_cost": 0.0005,
  "close_cost": 0.0015,
  "min_cost": 5,
  "execution_note": "Qlib daily executor with target-weight adapter"
}
```

## 不建议 V1 做的事

- 不直接生成 Qlib YAML。
- 不把 parser 输出变成任意 Qlib 表达式。
- 不同时支持自研 engine 和 Qlib engine 两套主链路。
- 不在 UI 中直接调用 Qlib。

## 官方参考

- Qlib Portfolio Strategy: https://github.com/microsoft/qlib/blob/main/docs/component/strategy.rst
- Qlib Workflow: https://qlib.readthedocs.io/en/stable/component/workflow.html
- Qlib Evaluation & Results Analysis: https://qlib.readthedocs.io/en/v0.9.5/component/report.html
