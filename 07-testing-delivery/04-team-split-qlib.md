# Qlib 版五人分工

## 总体节奏

先由 2 人完成数据与内核闭环，再由 3 人做 UI 和演示集成。

```text
第 1 段：数据 / 内核
  人员 A：Qlib 数据层
  人员 B：策略编译 + Qlib 评测内核

第 2 段：UI / 集成
  人员 C：输入与解析体验
  人员 D：结果展示与图表
  人员 E：集成、错误处理、答辩 demo
```

## 人员 A：Qlib 数据层

### 负责范围

- Qlib 初始化
- 数据目录配置
- 交易日历
- 股票池解析
- 行情读取
- symbol 标准化
- capability summary

### 主要文件

- `src/config.py`
- `src/symbols.py`
- `src/data_provider.py`
- `src/qlib_provider.py`
- `scripts/prepare_qlib_data.md`
- `tests/test_qlib_provider.py`

### 对外接口

人员 A 交给其他人的稳定接口：

- `get_calendar(start, end)`
- `get_bars(symbols, start, end, fields=None)`
- `resolve_universe(universe_spec, start, end)`
- `get_capabilities()`
- `build_market_state(date, universe)`

### 完成标准

- 能读取 `SH600036`。
- 能解析 `csi300`。
- provider_uri 缺失时能给出可读错误。
- capability summary 能进入 `BacktestResult`。

## 人员 B：策略编译与 Qlib 评测内核

### 负责范围

- 指标函数
- DSL compiler
- `CompiledStrategy`
- Qlib target-weight adapter
- Qlib evaluator
- report 转换

### 主要文件

- `src/indicators.py`
- `src/compiler.py`
- `src/qlib_strategy_adapter.py`
- `src/qlib_evaluator.py`
- `src/report.py`
- `tests/test_compiler.py`
- `tests/test_qlib_single_asset.py`
- `tests/test_qlib_cross_sectional.py`

### 对外接口

人员 B 交给 UI 的稳定接口：

- `compile_strategy(dsl) -> CompiledStrategy`
- `run_backtest(parse_result, config) -> BacktestResult`

### 完成标准

- 单股策略能跑出 Qlib report。
- 横截面策略能跑出 Qlib positions。
- `BacktestResult` 不暴露必须由 UI 理解的 Qlib 内部对象。
- metrics 至少包含 annualized return、max drawdown、information ratio 或 sharpe。

## 人员 C：UI 输入与解析体验

### 负责范围

- Streamlit 页面骨架
- 两个 tab
- 输入表单
- parser 调用
- DSL JSON 展示
- assumptions / warnings 展示

### 主要文件

- `app/streamlit_app.py`
- `app/ui_inputs.py`（可选）

### 完成标准

- 单股 tab 可输入 `SH600036` 或 `600036.SH`。
- 横截面 tab 可选择 `csi300` 或输入 symbol list。
- 解析结果清晰展示，不执行回测。

## 人员 D：UI 结果展示与图表

### 负责范围

- metrics 卡片
- 净值 / benchmark 图
- cost / turnover 图或摘要
- trades / positions / rebalances 表格
- capability summary 展示

### 主要文件

- `app/ui_results.py`（可选）
- `app/streamlit_app.py`

### 完成标准

- 能展示 `BacktestResult` 的所有关键字段。
- 图表不依赖 Qlib 原生对象，只吃已经转换后的数据。
- capability summary 中能看到 provider_uri、benchmark、exchange_kwargs。

## 人员 E：UI 集成、错误处理与答辩 demo

### 负责范围

- parser -> compiler -> qlib_evaluator -> UI 串联
- 数据错误处理
- demo 默认样例
- README 演示说明
- 最终验收清单

### 主要文件

- `app/streamlit_app.py`
- `sample_data/demo_pool_csi300_small.csv`
- `README.md`
- `tests/test_golden_cases.py`

### 完成标准

- 一键跑通单股 demo。
- 一键跑通横截面 demo。
- provider_uri 缺失、symbol 不存在、parser 失败都有友好提示。
- 答辩时能解释 Qlib 数据、Qlib adapter、Qlib risk_analysis 的位置。

## 接口冻结点

UI 三人开工前，必须确认以下对象已经稳定：

```python
ParseResult
BacktestResult
CapabilitySet
UniverseSpec
CompiledStrategy.generate_target_weights
```

## 每日同步建议

- 数据/内核阶段：每天同步一次 `BacktestResult` 字段是否变化。
- UI 阶段：每天同步一次 demo 输入、默认日期和默认股票池。
- 最终阶段：只修主链路和展示问题，不扩新策略原语。
