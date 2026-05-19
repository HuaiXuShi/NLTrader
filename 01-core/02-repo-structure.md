# 推荐代码仓库结构

目标：**尽量扁平、方便 Codex / Cursor 分文件生成、避免过早分层过深。**

```text
project/
├── app/
│   └── streamlit_app.py
├── src/
│   ├── models.py
│   ├── config.py
│   ├── data_provider.py
│   ├── qlib_provider.py
│   ├── qlib_strategy_adapter.py
│   ├── qlib_evaluator.py
│   ├── symbols.py
│   ├── indicators.py
│   ├── dsl.py
│   ├── parser.py
│   ├── compiler.py
│   ├── metrics.py
│   ├── report.py
│   └── sample_strategies.py
├── tests/
│   ├── test_parser.py
│   ├── test_compiler.py
│   ├── test_qlib_single_asset.py
│   ├── test_qlib_cross_sectional.py
│   └── test_golden_cases.py
├── sample_data/
├── docs/
├── .env.example
├── pyproject.toml
└── README.md
```

## 文件职责建议

### `src/models.py`
放所有跨模块共用的结构定义：
- bars schema 描述
- parse result
- capability set
- result object
- portfolio state

### `src/config.py`
只放配置读取与默认值：
- API endpoint / key
- Qlib `provider_uri`
- Qlib `region`
- benchmark，如 `SH000300`
- 交易成本参数
- 默认市场规则开关

### `src/data_provider.py`
抽象接口与规范。

### `src/qlib_provider.py`
Qlib 具体数据实现。  
只负责“初始化 Qlib + 读取数据 + 规范化 + capability 声明”，不负责业务逻辑。

### `src/qlib_strategy_adapter.py`
把 `CompiledStrategy.generate_target_weights(...)` 接到 Qlib target-weight 策略接口。

### `src/qlib_evaluator.py`
调用 Qlib 回测与 `risk_analysis`，把 Qlib 原始结果转换成 `BacktestResult`。

### `src/symbols.py`
处理股票代码标准化。  
UI 可以接收 `600036.SH`，内部统一成 Qlib 风格 `SH600036`。

### `src/indicators.py`
统一指标函数。  
避免指标散落在 parser / compiler / Qlib adapter 里。

### `src/dsl.py`
DSL schema、枚举、校验基础。

### `src/parser.py`
LLM 调用、prompt 组织、结构化解析、repair。

### `src/compiler.py`
把 DSL 编译成 `CompiledStrategy`。

### `src/metrics.py`
薄封装 Qlib 评测指标到 UI 需要的命名；不要重复实现 Qlib 已经给出的核心指标。

### `src/report.py`
把 `BacktestResult` 整理为前端更容易吃的结构。

### `src/sample_strategies.py`
放几个示例策略输入与示例 DSL，便于 demo 与测试。

## 为什么不建议第一版拆更多包

因为会让 Codex / Cursor 做过度抽象：
- service 层太早细分
- entity / repository / usecase 全套搬出来
- 反而更重

第一版应该允许“一个文件做一件比较完整的事”，而不是追求架构美感。
