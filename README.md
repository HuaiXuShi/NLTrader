# A股自然语言回测系统（Qlib 数据与评测版）文档包

这套文档面向 **Codex / Cursor / 开发团队**，目标不是描述一个“大而全产品”，而是把当前已经对齐的方案压缩成一套 **轻量、可开发、可扩展** 的实现蓝图。

一句话定义：

> 用自然语言描述 A 股日频策略，系统通过 LLM 解析成受控 DSL，再编译为目标权重策略，最后使用 Qlib 数据、Qlib 执行/评测能力完成单股时序或股票池横截面策略回测，并给出结果与解释。

## 当前已拍板的核心方向

- 市场：A 股
- 频率：日频
- 方向：long-only
- 用户入口：自然语言
- 策略模式：  
  - 单股时序策略  
  - 股票池横截面选股策略
- 内核形态：**统一 target-weight 策略接口 + Qlib WeightStrategyBase / backtest / risk_analysis 适配层**
- 数据方案：以 **Qlib provider_uri + CN A-share 数据目录** 为默认起点
- LLM 方案：**完全依赖 API**，但要做 provider-agnostic 接口
- 前端：**单页 Streamlit**，用两个 tab 覆盖两类策略
- 质量控制：**契约优先 + golden cases + 少量高价值测试**
- 非目标：不做分钟级、不做实盘、不做全市场超复杂选股平台、不让 LLM 直接生成可执行策略代码

## 这套文档怎么读

建议顺序：

1. `README.md`
2. `START-HERE-FOR-CODEX.md`
3. `DECISIONS-AT-A-GLANCE.md`
4. `00-overview/`
5. `01-core/`
6. `02-data/`
7. `03-dsl/`
8. `04-parser/`
9. `05-engine/`
10. `06-app/`
11. `07-testing-delivery/`

## 目录结构

```text
a-share-nl-backtester-lite-docs/
├── README.md
├── START-HERE-FOR-CODEX.md
├── FILE-INDEX.md
├── DECISIONS-AT-A-GLANCE.md
├── 00-overview/
├── 01-core/
├── 02-data/
├── 03-dsl/
├── 04-parser/
├── 05-engine/
├── 06-app/
└── 07-testing-delivery/
```

## 这版文档的设计原则

1. **先锁边界，再谈扩展**
2. **统一抽象优先于模板堆砌**
3. **用一个 target-weight adapter 覆盖时序与横截面**
4. **让 LLM 只做理解，不做交易逻辑**
5. **对数据能力缺失要显式降级，不要假装支持**
6. **为了 Codex / Cursor，把模块切小，把契约写清**

## 最重要的四个抽象

- `DataProvider`
- `StrategyDSL`
- `CompiledStrategy.generate_target_weights(...)`
- `BacktestResult`

只要这四个抽象不乱，后面无论增加指标、扩展股票池、替换 LLM、补市场规则，都不需要推翻整个系统。

## Qlib 版改动重点

- 使用 `qlib.init(provider_uri=..., region=REG_CN)` 初始化本地 Qlib 数据。
- 使用 `qlib.data.D.calendar / D.instruments / D.list_instruments / D.features` 获取日历、股票池和行情字段。
- 内部股票代码统一采用 Qlib 风格，如 `SH600036`、`SZ000001`；UI 可接受 `600036.SH` 并在入口标准化。
- 策略仍统一输出目标权重，优先通过继承 `qlib.contrib.strategy.WeightStrategyBase` 接入 Qlib 回测。
- 评测输出以 Qlib `report_normal`、`positions_normal`、`risk_analysis` 为主，再转换为 UI 需要的 `BacktestResult`。
