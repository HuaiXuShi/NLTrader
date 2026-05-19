# 文件索引

## 根目录

| 文件 | 作用 |
|---|---|
| `README.md` | 文档包总览与阅读顺序 |
| `START-HERE-FOR-CODEX.md` | 给 Codex / Cursor 的开发起始说明 |
| `FILE-INDEX.md` | 当前文件索引 |
| `DECISIONS-AT-A-GLANCE.md` | 已拍板的架构决策和默认值 |

## 00-overview

| 文件 | 作用 |
|---|---|
| `00-overview/README.md` | 模块说明 |
| `00-overview/01-one-pager.md` | 一页纸产品定义 |
| `00-overview/02-scope-and-boundary.md` | 做什么 / 不做什么 |
| `00-overview/03-user-flows.md` | 两类用户流程与 demo 路径 |

## 01-core

| 文件 | 作用 |
|---|---|
| `01-core/README.md` | 模块说明 |
| `01-core/01-core-abstractions.md` | 四个核心抽象与关键数据结构 |
| `01-core/02-repo-structure.md` | 推荐代码仓库结构 |
| `01-core/03-minimal-extension-rules.md` | 如何轻量扩展而不推翻骨架 |

## 02-data

| 文件 | 作用 |
|---|---|
| `02-data/README.md` | 模块说明 |
| `02-data/01-data-provider-contract.md` | 数据接口契约 |
| `02-data/02-qlib-data-plan.md` | Qlib 数据初始化、读取、缓存边界和样本方案 |
| `02-data/03-capabilities-and-fallbacks.md` | 数据能力标记与降级逻辑 |
| `02-data/04-data-shape-and-sample-files.md` | 规范化数据形状与开发样本 |

## 03-dsl

| 文件 | 作用 |
|---|---|
| `03-dsl/README.md` | 模块说明 |
| `03-dsl/01-dsl-overview.md` | DSL 总体设计 |
| `03-dsl/02-timeseries-strategy-spec.md` | 单股时序策略 DSL |
| `03-dsl/03-cross-sectional-strategy-spec.md` | 横截面选股策略 DSL |
| `03-dsl/04-validation-assumptions-warnings.md` | 校验、默认假设、警告机制 |
| `03-dsl/05-example-strategies.md` | 输入样例与预期解析方向 |

## 04-parser

| 文件 | 作用 |
|---|---|
| `04-parser/README.md` | 模块说明 |
| `04-parser/01-parser-workflow.md` | LLM 解析流水线 |
| `04-parser/02-llm-api-contract.md` | API 接入契约 |
| `04-parser/03-prompt-and-output-policy.md` | Prompt 策略与输出规范 |

## 05-engine

| 文件 | 作用 |
|---|---|
| `05-engine/README.md` | 模块说明 |
| `05-engine/01-engine-flow.md` | Qlib 评测内核主流程 |
| `05-engine/02-execution-and-a-share-rules.md` | 执行模型与 A 股规则 |
| `05-engine/03-portfolio-metrics-and-report.md` | 结果对象、指标和报告内容 |
| `05-engine/04-qlib-evaluation-adapter.md` | Qlib 策略适配、回测调用与评测映射 |

## 06-app

| 文件 | 作用 |
|---|---|
| `06-app/README.md` | 模块说明 |
| `06-app/01-streamlit-layout.md` | 单页 Streamlit 设计 |
| `06-app/02-ui-state-and-data-contract.md` | UI 状态与接口契约 |

## 07-testing-delivery

| 文件 | 作用 |
|---|---|
| `07-testing-delivery/README.md` | 模块说明 |
| `07-testing-delivery/01-golden-cases.md` | 高价值回归样例 |
| `07-testing-delivery/02-build-plan-for-codex-cursor.md` | 开发顺序和任务拆解 |
| `07-testing-delivery/03-acceptance-checklist.md` | 验收清单 |
| `07-testing-delivery/04-team-split-qlib.md` | 2 人数据/内核 + 3 人 UI 的详细分工 |
