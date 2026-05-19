# 给 Codex / Cursor 的 Qlib 版开发计划

## 总体策略

按“先契约、再 Qlib 数据、再 Qlib 评测内核、后 parser、最后 UI”的顺序推进。  
下一步人员安排固定为：

- 2 人先做数据与内核。
- 3 人在核心接口稳定后做 UI、集成和演示。

这份计划的核心不是把 Qlib 全部能力搬进来，而是把自然语言策略稳定接到 Qlib 数据与评测链路。

---

## Step 0：共同冻结接口

### 目标

所有人先对齐几个不会轻易变的结构，避免并行时互相打架。

### 必须冻结

- `ParseResult`
- `StrategyDSL`
- `CompiledStrategy.generate_target_weights(...)`
- `CapabilitySet`
- `BacktestResult`
- symbol 规范：内部统一 `SH600036` / `SZ000001`

### 交付物

- `src/models.py`
- `src/dsl.py`
- `src/symbols.py`

### 提示词

```text
请根据 docs/01-core/01-core-abstractions.md、docs/02-data/01-data-provider-contract.md 和 docs/03-dsl/* 实现核心模型、DSL 校验和 symbol 标准化。
要求：
1. 内部 symbol 统一使用 Qlib 风格，如 SH600036、SZ000001
2. UI 兼容输入 600036.SH，但必须转换后再进入 DSL
3. 定义 ParseResult、BacktestResult、CapabilitySet、UniverseSpec、MarketState、PortfolioState
4. 不接 Qlib，不接 LLM，不写 UI
```

---

## Step 1：项目脚手架与环境

### 目标

创建最小 Python 项目结构，并准备 Qlib 配置入口。

### 交付物

- `pyproject.toml`
- `.env.example`
- `src/config.py`
- `scripts/prepare_qlib_data.md`

### 依赖建议

- `pyqlib`
- `pandas`
- `numpy`
- `plotly`
- `streamlit`
- `pydantic` 或 dataclass 二选一
- `pytest`

### 提示词

```text
请根据 docs/01-core/02-repo-structure.md 创建一个 Qlib 版最小 Python 项目骨架。
要求：
1. 使用 src 布局
2. 创建 app、src、tests、sample_data、scripts 目录
3. .env.example 包含 QLIB_PROVIDER_URI、QLIB_REGION、QLIB_BENCHMARK、LLM_API_KEY、LLM_BASE_URL
4. scripts/prepare_qlib_data.md 写清楚 Qlib 数据准备命令
5. 不实现业务逻辑
```

---

## Step 2：数据层（人员 A）

### 目标

实现 `QlibDataProvider`，让核心层能稳定拿到日历、行情、股票池和 capability summary。

### 交付物

- `src/data_provider.py`
- `src/qlib_provider.py`
- `tests/test_qlib_provider.py`

### 提示词

```text
请根据 docs/02-data/* 实现 QlibDataProvider。
要求：
1. 封装 qlib.init(provider_uri, region=REG_CN)
2. 用 qlib.data.D.calendar 获取交易日历
3. 用 D.instruments / D.list_instruments 解析 qlib_market，如 csi300
4. 用 D.features 读取 $open、$high、$low、$close、$volume
5. 输出统一 BarsFrame：date、symbol、open、high、low、close、volume、amount
6. get_capabilities() 返回 provider_uri、region、benchmark、是否有 benchmark、是否使用 Qlib CN region
7. provider_uri 缺失时返回可读错误，不要让 traceback 直接进入 UI
```

### 验收

- 能初始化 Qlib。
- 能读取 `SH600036` 的日频数据。
- 能解析 `csi300` 的股票池。
- 能返回 capability summary。

---

## Step 3：策略编译与指标（人员 B）

### 目标

把 DSL 编译为统一目标权重策略。

### 交付物

- `src/indicators.py`
- `src/compiler.py`
- `tests/test_compiler.py`

### 提示词

```text
请根据 docs/03-dsl/* 实现指标函数与 DSL compiler。
要求：
1. 支持 SMA、EMA、RSI、MACD、BOLL、RETURN_N、VOL_MA_RATIO
2. 支持 timeseries entry_rules / exit_rules
3. 支持 cross_sectional filters、score、rank、top_n、equal_weight
4. 编译后统一提供 generate_target_weights(date, market_state, portfolio_state)
5. 不调用 Qlib backtest，不写 UI
```

### 验收

- 单股均线策略能输出 `{SH600036: 1.0}` 或 `{}`。
- 横截面 top N 动量策略能输出等权目标持仓。
- long-only 和权重和不超过 1 的校验清晰。

---

## Step 4：Qlib 评测内核（人员 B，与人员 A 对接）

### 目标

把 `CompiledStrategy` 接到 Qlib 策略与评测。

### 交付物

- `src/qlib_strategy_adapter.py`
- `src/qlib_evaluator.py`
- `src/report.py`
- `tests/test_qlib_single_asset.py`
- `tests/test_qlib_cross_sectional.py`

### 提示词

```text
请根据 docs/05-engine/* 实现 Qlib 评测适配层。
要求：
1. 实现 QlibTargetWeightStrategy，职责是调用 compiled_strategy.generate_target_weights()
2. 优先继承或包装 qlib.contrib.strategy.WeightStrategyBase
3. 实现 QlibEvaluator，统一配置 benchmark、deal_price、limit_threshold、open_cost、close_cost、min_cost
4. 调用 Qlib backtest 或 backtest_daily
5. 调用 risk_analysis 得到 annualized_return、information_ratio、max_drawdown 等指标
6. 转换为 BacktestResult，保留 qlib_report、qlib_positions、qlib_analysis
7. capability_summary 必须显示 provider_uri、region、benchmark、exchange_kwargs
```

### 验收

- 单股策略能跑出 Qlib report。
- 横截面策略能跑出 Qlib positions。
- metrics 中至少有 return、annualized_return、max_drawdown、information_ratio 或 sharpe。
- UI 不需要知道任何 Qlib 原生对象。

---

## Step 5：Parser

### 目标

接上外部 API，把自然语言转成 DSL。

### 交付物

- `src/parser.py`
- `tests/test_parser.py`

### 提示词

```text
请根据 docs/04-parser/* 实现轻量 parser。
要求：
1. 接收自然语言和可选上下文
2. 调用 OpenAI 风格兼容的 LLM API
3. 产出 ParseResult
4. symbol 输出使用 Qlib 风格
5. 支持 schema 校验、semantic 校验和最多一次 repair
6. API 失败时允许有限 fallback parser，但必须给 warning
7. 绝不生成可执行代码或 Qlib YAML
```

---

## Step 6：UI 第一人：输入与解析面板

### 目标

搭建 Streamlit 页面框架、两个 tab、输入表单和解析结果展示。

### 交付物

- `app/streamlit_app.py`
- `app/ui_inputs.py`（可选）

### 提示词

```text
请根据 docs/06-app/* 实现 Streamlit 输入与解析面板。
要求：
1. 两个 tab：单股时序策略、股票池横截面策略
2. 单股 tab 支持 SH600036 和 600036.SH
3. 横截面 tab 支持 qlib_market=csi300 和手工 symbol list
4. 点击解析后展示 human_summary、assumptions、warnings、DSL JSON
5. 不调用 Qlib，不执行回测，只接 parser
```

---

## Step 7：UI 第二人：回测结果与图表

### 目标

展示 `BacktestResult`。

### 交付物

- `app/ui_results.py`（可选）
- 图表渲染函数

### 提示词

```text
请根据 docs/05-engine/03-portfolio-metrics-and-report.md 和 docs/06-app/* 实现结果展示。
要求：
1. 展示 metrics 卡片
2. 展示策略净值和 benchmark 曲线
3. 展示 cost、turnover 或 Qlib risk_analysis 摘要
4. 单股展示买卖/持仓记录
5. 横截面展示 positions 和 rebalances
6. 显示 qlib provider_uri、benchmark、exchange_kwargs
```

---

## Step 8：UI 第三人：集成、错误处理与演示脚本

### 目标

把 parser、compiler、Qlib evaluator 和 UI 串起来，保证答辩可演示。

### 交付物

- `app/streamlit_app.py`
- `sample_data/demo_pool_csi300_small.csv`
- `README.md` demo 说明

### 提示词

```text
请完成 UI 集成与演示路径。
要求：
1. Run 按钮按 parser -> compiler -> qlib_evaluator 顺序执行
2. provider_uri 缺失、Qlib 初始化失败、symbol 不存在时显示清晰错误
3. 内置两个 demo：单股均线策略、月度动量 top N 策略
4. 页面始终显示当前数据源、benchmark、能力摘要和边界说明
5. 不把 traceback 直接展示给用户
```

---

## Step 9：测试与 golden cases

### 目标

用少量高价值测试锁住主链路。

### 交付物

- `tests/test_parser.py`
- `tests/test_compiler.py`
- `tests/test_qlib_provider.py`
- `tests/test_qlib_single_asset.py`
- `tests/test_qlib_cross_sectional.py`
- `tests/test_golden_cases.py`

### 提示词

```text
请根据 docs/07-testing-delivery/01-golden-cases.md 为 Qlib 版项目生成最小但高价值的测试集。
要求：
1. 覆盖 timeseries / cross_sectional 两类策略
2. 覆盖 assumptions / warnings
3. 覆盖 Qlib provider_uri 缺失的错误
4. 覆盖 capability summary
5. 覆盖 BacktestResult 中 qlib_report、qlib_positions、qlib_analysis 字段
```

## 并行协作原则

- 数据与内核两人先行，优先冻结接口。
- UI 三人只在 `ParseResult` 和 `BacktestResult` 稳定后开工。
- UI 不直接 import Qlib。
- Qlib 配置只从 `config.py` 读取。
- 所有 demo 示例使用同一组 symbol 和日期，避免各自调不同数据导致演示不一致。
