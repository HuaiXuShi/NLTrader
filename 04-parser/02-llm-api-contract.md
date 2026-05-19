# LLM API 接入契约

## 目标

让 parser 不绑死到某一家模型服务。  
第一版默认使用“OpenAI 风格兼容”的 chat completion API 约定，但代码上应尽量 provider-agnostic。

## 配置项建议

```text
LLM_API_BASE=
LLM_API_KEY=
LLM_MODEL=
LLM_TIMEOUT_SECONDS=
LLM_TEMPERATURE=
```

## 推荐请求接口

```python
class LLMClient:
    def complete_json(self, system_prompt: str, user_prompt: str) -> dict:
        ...
```

parser 不应该直接关心 HTTP 细节，只关心这个接口。

## 请求内容建议

### system prompt
写死系统能力边界：
- 仅支持 A 股日频
- 输出必须是合法 JSON
- 只允许使用支持的字段和值

### user prompt
传入：
- 用户自然语言
- 可选上下文（股票代码、股票池来源、回测区间）
- 支持字段清单摘要

## 响应要求

模型必须返回一个 JSON 对象，包含至少：

```json
{
  "strategy_kind": "timeseries",
  "dsl": {},
  "assumptions": [],
  "warnings": [],
  "human_summary": "",
  "parse_confidence": 0.85
}
```

## 错误处理建议

### 网络错误
- 返回 API 不可用错误
- 尝试 fallback parser（若启用）
- 在 UI 中显示简洁说明

### 非 JSON 输出
- 先做文本清洗
- 再尝试一次 repair
- 不行则报错

### JSON 结构不完整
- 做 schema 错误汇总
- 如果可修复则 repair 一次
- 否则失败

## 安全边界

即使模型输出了：
- Python 代码
- 新字段
- 未支持指标
- 分钟级策略

也必须由 parser / validator 拦住，不能直接进入 compiler。

## 建议的版本控制

给 prompt / supported DSL 标一版号，例如：

- `dsl_version = v1`
- `prompt_version = p1`

这能帮助后面定位“某次模型行为变化是不是因为 prompt 更新”。
