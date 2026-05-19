# START HERE FOR CODEX / CURSOR

这份文件是给自动开发代理看的。目标不是一次性生成“最终系统”，而是按顺序把最小闭环做通。

## 一句话目标

先做出这条主链路：

> 自然语言 → 解析为 DSL → 编译策略 → 回测 → 展示结果

并且同时覆盖：

- 单股时序策略
- 股票池横截面选股策略

## 必须遵守的实现约束

### 1. 不要过度工程化
不要一开始引入：
- 前后端分离
- 微服务
- 复杂数据库
- 过度抽象的插件系统
- 多余的依赖注入框架

第一版只需要：
- `src/*.py`
- `app/streamlit_app.py`
- `tests/`
- 本地 Qlib 数据目录配置

### 2. 一定要用统一目标权重接口
单股和选股都必须落到同一个接口：

`CompiledStrategy.generate_target_weights(date, market_state) -> dict[symbol, weight]`

不要写两套完全独立的策略执行逻辑。Qlib 适配层负责把目标权重接入 `WeightStrategyBase` 或等价回测入口。

### 3. LLM 不能直接生成可执行代码
LLM 只允许输出：
- 结构化 DSL
- assumptions
- warnings
- parse_confidence
- 人类可读解释摘要

LLM 不允许输出：
- 可执行 Python
- Qlib YAML
- Qlib 表达式

### 4. 数据源要 provider 化
第一版默认 Qlib，但业务逻辑不能写死到 `qlib.data.D` 调用上。

业务层只依赖 `DataProvider`，Qlib 只出现在：
- `src/qlib_provider.py`
- `src/qlib_strategy_adapter.py`
- `src/qlib_evaluator.py`
- 配置和启动脚本

### 5. 对数据能力不足必须降级
如果数据源缺少：
- 停牌信息
- 涨跌停价
- 动态指数成分股
- 原始价/复权价双序列或需要的成交字段

系统必须：
- 给出 warning
- 使用文档中定义的 fallback 逻辑
- 在结果里显示 capability summary

### 6. 先做契约，再做页面
优先顺序固定如下。

## 推荐开发顺序

### Phase 1：骨架与契约
先写：
- `src/models.py`
- `src/dsl.py`
- `src/config.py`

### Phase 2：数据层
再写：
- `src/data_provider.py`
- `src/qlib_provider.py`
- `src/symbols.py`
- `scripts/prepare_qlib_data.md` 或等价数据准备说明

### Phase 3：策略与指标
再写：
- `src/indicators.py`
- `src/compiler.py`

### Phase 4：先打通 Qlib 评测内核
再写：
- `src/qlib_strategy_adapter.py`
- `src/qlib_evaluator.py`
- `src/metrics.py`
- `src/report.py`

### Phase 5：扩展到横截面选股
仍然用同一个 `generate_target_weights` 接口，只扩策略编译和组合构建。

### Phase 6：接 LLM Parser
再写：
- `src/parser.py`

### Phase 7：Streamlit
最后写：
- `app/streamlit_app.py`

### Phase 8：测试和 golden cases
再补：
- `tests/`

## 第一版什么叫完成

系统至少应满足：

1. 能输入一句中文策略
2. 能解析成结构化 DSL
3. 能显示 assumptions / warnings
4. 能跑一条单股时序回测
5. 能跑一条股票池横截面回测
6. 能返回 Qlib 风格评测结果、关键指标、持仓/调仓记录
7. 能在 UI 中完整演示

## 禁止事项

- 不要把“各种策略都支持”理解成无限制支持任意中文
- 不要做分钟级
- 不要支持做空 / 杠杆 / 实盘
- 不要在第一版做全市场复杂选股
- 不要依赖人工逐行 code review 才能保证质量

## 质量控制方式

优先使用：
- 明确的数据契约
- DSL schema
- golden cases
- 小而稳的测试集
- sample strategies

而不是靠大家事后猜代码对不对。
