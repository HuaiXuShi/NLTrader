# Parser 工作流

## 目标

把用户自然语言稳定地转成 `ParseResult`。

## 推荐流水线

```text
用户输入
  ↓
PromptBuilder 组装系统提示与支持范围
  ↓
LLM API 调用
  ↓
Raw JSON 解析
  ↓
Schema 校验
  ↓
Semantic 校验
  ↓
可选一次 repair
  ↓
输出 ParseResult
```

## 详细步骤

### 1. 输入标准化
先清理：
- 多余空格
- 中文标点
- 股票代码格式中的空白
- 明显的重复语句

### 2. PromptBuilder
明确告诉模型：
- 当前支持 A 股日频
- 支持两类策略：timeseries / cross_sectional
- 支持哪些指标、操作符、调仓频率
- 不支持哪些场景
- 只能输出 JSON

### 3. LLM 调用
建议：
- `temperature` 低
- 强制 JSON 输出（若 API 支持）
- 模型名称、endpoint、key 由配置注入

### 4. Raw JSON 解析
如果返回包含 markdown code fence，应先去掉。

### 5. Schema 校验
检查顶层字段和类型。

### 6. Semantic 校验
检查：
- timeseries 是否缺 signal
- cross_sectional 是否缺 universe
- 指标 / 操作符是否在支持清单里
- `top_n` 是否合理

### 7. Repair（最多一次）
仅允许轻微修复：
- 缺少外层 wrapper
- 字段名拼写相近修正
- 枚举大小写修正

### 8. 输出 ParseResult
包括：
- dsl
- strategy_kind
- assumptions
- warnings
- human_summary
- parse_confidence

## fallback parser 建议

由于项目完全依赖 API，但答辩存在不稳定风险，建议保留一个非常轻量的 fallback：

- 基于关键词判断 `timeseries / cross_sectional`
- 支持 2~3 个最常见模板
- API 失败时给出“有限 fallback 解析”警告

这不替代主 parser，但能避免现场演示完全失败。

## 日志建议

记录：
- 原始输入
- 发送给模型的支持范围版本号
- 原始模型输出
- repair 前后结果
- 最终 parse result

便于排查“是 prompt 问题还是 compiler 问题”。
