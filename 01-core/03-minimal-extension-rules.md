# 轻量扩展规则

这个文件定义的是：以后如果要扩功能，怎么扩才不会把轻量骨架弄坏。

## 规则 1：新增指标，不新增评测内核
如果想支持：
- 新均线
- 新动量指标
- 新波动率指标

应该只改：
- `indicators.py`
- `dsl.py`（指标枚举）
- `compiler.py`
- 相关测试

不应该改：
- Qlib adapter / evaluator 主流程
- UI 主结构

## 规则 2：新增策略语义，优先扩 DSL 原语
比如想支持：
- `ATR`
- `CCI`
- `top_k_by_factor`

优先在 DSL 中增加新原语，而不是新增一个“ATR 策略模板类”“CCI 策略模板类”。

## 规则 3：新增股票池类型，优先扩 universe resolver
比如未来支持：
- 动态指数成分股
- 行业池
- 自定义标签池

应该优先扩：
- `UniverseSpec`
- `DataProvider.resolve_universe(...)`

而不是写新的 Qlib adapter。

## 规则 4：新增数据源，不改业务层
比如未来支持 Tushare：
- 新建 `tushare_provider.py`
- 保持 `DataProvider` 接口不变

不应该让 compiler / Qlib adapter / app 直接依赖新数据源接口。
在 Qlib 版中，也不应该让 compiler / app 直接依赖 `qlib.data.D`。

## 规则 5：新增 LLM，不改 parser 输出契约
未来可以换不同 API 提供方，但 `ParseResult` 不能乱变。

## 规则 6：UI 功能扩展只能消费已有结果结构
不要让 Streamlit 页面去直接算指标、直接解析 DSL、直接操作 provider。

## 规则 7：遇到高复杂功能，先做 capability-based degrade
例如：
- 没有涨跌停数据
- 没有动态成分股

优先：
1. 降级
2. 告警
3. 结果页显示说明

而不是为了“完整支持”一下子重构系统。

## 规则 8：什么时候可以考虑重构

只有满足以下任一情况，再考虑把扁平结构升级为 package 结构：

- 文件数量显著增加
- 指标种类超过几十个
- parser provider 需要支持多家
- app 变成多页面 / API 并存
- 团队协作需要更细职责分工

第一版不需要为了“以后可能扩展”提前做重构。
