# 04-parser

这一组文件定义 LLM 解析层怎么工作。

Parser 的职责非常克制：

- 读自然语言
- 生成 DSL
- 做结构化修复和校验
- 产出 assumptions / warnings

它不负责：
- 直接交易
- 写 Python 策略代码
- 拉市场数据
- 算回测结果

推荐顺序：

1. `01-parser-workflow.md`
2. `02-llm-api-contract.md`
3. `03-prompt-and-output-policy.md`
