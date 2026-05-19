# 验收清单

## A. 项目级验收

- [ ] 能输入自然语言策略
- [ ] 能识别 `timeseries` 或 `cross_sectional`
- [ ] 能输出结构化 DSL
- [ ] 能输出 assumptions / warnings
- [ ] 能跑通单股时序回测
- [ ] 能跑通股票池横截面回测
- [ ] UI 能完整演示两类策略

## B. 数据层验收

- [ ] DataProvider 抽象存在
- [ ] QlibDataProvider 可运行
- [ ] provider_uri / region / benchmark 可配置
- [ ] symbol 格式统一
- [ ] 能返回 capability summary
- [ ] 能解析 Qlib market，如 `csi300`

## C. DSL / Parser 验收

- [ ] DSL 顶层结构固定
- [ ] 支持两类 strategy_kind
- [ ] 支持基础指标和操作符
- [ ] parser 不输出可执行代码
- [ ] parser 能拒绝明显超范围请求
- [ ] parser 能输出 human_summary

## D. Qlib 内核验收

- [ ] 单股与横截面使用同一 Qlib adapter
- [ ] 支持 Qlib 日频执行
- [ ] 支持 long-only
- [ ] 支持交易成本
- [ ] 支持 benchmark
- [ ] capability 缺失时能降级而不是崩溃
- [ ] BacktestResult 保留 qlib_report、qlib_positions、qlib_analysis

## E. 报告与 UI 验收

- [ ] 显示 metrics
- [ ] 显示净值曲线
- [ ] 显示 assumptions / warnings
- [ ] 显示 capability summary
- [ ] 单股页显示买卖记录
- [ ] 横截面页显示调仓记录

## F. 测试验收

- [ ] 至少覆盖 5~10 个高价值 golden cases
- [ ] 覆盖 parser 成功与失败场景
- [ ] 覆盖 Qlib adapter 的单股与横截面主链路
- [ ] 覆盖至少一种 capability 降级场景

## G. 答辩验收

- [ ] 准备好一个单股示例
- [ ] 准备好一个横截面示例
- [ ] 能解释为什么使用统一 target-weight adapter
- [ ] 能解释 LLM 在系统中的位置
- [ ] 能解释当前未支持范围
- [ ] 能解释数据能力不足时如何降级
- [ ] 能解释 Qlib 数据、Qlib 回测和 risk_analysis 的口径

## H. 如果时间只剩最后一天，优先保什么

必须保住：

1. parser → DSL
2. 单股时序回测
3. 一个横截面策略样例
4. assumptions / warnings
5. UI 可演示

可以放弃或弱化：
- 复杂图表
- 严格 lot size
- 更完整 market rules
- 太多策略示例
