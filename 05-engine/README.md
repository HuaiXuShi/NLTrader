# 05-engine

这一组文件定义 Qlib 评测内核怎么运行。

最重要的设计点只有一个：

> 不管是单股时序还是横截面选股，最后都由同一个 target-weight adapter 接入 Qlib 回测与评测。

推荐顺序：

1. `01-engine-flow.md`
2. `02-execution-and-a-share-rules.md`
3. `03-portfolio-metrics-and-report.md`
4. `04-qlib-evaluation-adapter.md`
