# Golden Cases

这些样例的作用不是验证精确数值，而是验证：
- parser 是否理解对了
- compiler 是否编译对了
- Qlib adapter / evaluator 是否按预期走通
- 降级逻辑是否透明

## Case 1：单股均线交叉

### 输入
5日均线上穿20日均线买入，跌破10日均线卖出。

### 期望
- 识别为 `timeseries`
- 生成 entry / exit rules
- Qlib 回测能跑完
- 至少生成若干 trade 或明确零交易

## Case 2：单股 + 止损

### 输入
5日均线上穿20日均线买入，亏损8%卖出。

### 期望
- `risk.stop_loss = 0.08`
- 策略编译能在目标权重中反映风险退出，Qlib 回测能跑通

## Case 3：模糊“放量”

### 输入
放量上涨时买入，趋势破了就卖。

### 期望
- 返回 assumptions
- 至少一条 warnings
- 不应该静默解析成完全确定的规则而不说明

## Case 4：月度动量 top N

### 输入
每月调仓，在股票池中选择过去20日涨幅最高的10只股票等权持有。

### 期望
- 识别为 `cross_sectional`
- `rebalance.freq = monthly`
- `score.factor = RETURN_N`
- `top_n = 10`

## Case 5：横截面缺少股票池

### 输入
每月选过去20日涨幅最高的10只股票等权持有。

### 期望
- 返回 warning 或 error
- 不应悄悄使用某个隐含全市场 universe

## Case 6：不支持分钟级

### 输入
5分钟均线上穿20分钟均线买入。

### 期望
- parser 拒绝或明确 unsupported
- Qlib evaluator 不执行

## Case 7：Qlib provider_uri 缺失

### 前提
本机没有配置 `QLIB_PROVIDER_URI` 或路径不存在

### 期望
- 返回 data error
- 提示如何准备 Qlib 数据
- 不把 traceback 直接展示给 UI

## Case 8：Qlib capability summary

### 前提
正常运行一条回测

### 期望
- capability summary 包含 provider_uri、region、benchmark、deal_price、limit_threshold、cost
- 回测能跑
- 用户能看到 Qlib 评测口径

## Case 9：API 失败的 fallback

### 前提
LLM API 调用失败

### 期望
- 系统给出简洁错误
- 若 fallback parser 启用，可用有限模板继续演示
- 必须有明显 warning：当前不是主解析模式

## Case 10：同一引擎跑两类策略

### 目标
验证：
- timeseries
- cross_sectional

都通过 `generate_target_weights()` 接口进入同一 Qlib adapter。  
这是架构正确性的关键。
