# 执行模型与 A 股规则

## 第一版执行模型

### 统一设定
- 执行频率：日频
- 策略输出：目标权重
- 回测执行：Qlib executor / exchange
- long-only

这是整个系统最重要的时间语义。V1 不再自研完整撮合循环，而是把自定义策略接入 Qlib。

## 必做规则

### 1. Qlib daily execution
使用 Qlib 日频 executor。默认 `deal_price` 推荐先设为 `close`，与 Qlib 官方示例保持一致，降低实现风险。

### 2. 信号滞后
如果要表达“t 日收盘产生信号，t+1 执行”，应在 `QlibTargetWeightStrategy` 内显式使用前一交易日信号或在测试中验证目标权重生成日期。

### 3. 交易成本
建议包含：
- `commission_rate`
- `stamp_duty_rate`（卖出时）
- 可选 `min_commission`

### 4. long-only
不允许负权重、卖空或杠杆。

### 5. benchmark
默认使用 `SH000300`，用于 Qlib excess return 和风险评测。

## 能力支持时启用的规则

### 1. 停牌不可交易
若 provider 有停牌信息：
- 停牌标的不执行买卖
- 记录失败原因

### 2. 涨跌停导致无法成交
优先使用 Qlib `limit_threshold` / exchange 配置。UI 只展示是否启用，不自行判断涨跌停。

### 3. raw / adjusted 分离
若 provider 有双序列：
- adjusted 用于信号
- raw 用于成交

否则记录降级 warning。

## 推荐失败原因枚举

```text
API_DATA_MISSING
NO_NEXT_OPEN_PRICE
T_PLUS_ONE_BLOCKED
SUSPENDED
UP_LIMIT_OPEN
DOWN_LIMIT_OPEN
INSUFFICIENT_CASH
ZERO_TARGET_WEIGHT
```

## 关于 lot size

Qlib CN region 默认交易单位为 100 股。项目只展示该配置，不重复实现。

## 成本计算建议

### 买入成本
- commission

### 卖出成本
- commission
- stamp duty

### 结果
Qlib evaluator 应在结果中明确记录：
- gross_amount
- fees
- net_amount

## 降级透明化

如果某些 A 股规则没有启用，必须在 `capability_summary` 中明确说明：

- 已启用：
  - qlib daily executor
  - transaction costs
  - benchmark
- 未启用：
  - minute-level execution
  - live trading

这样既轻量，又诚实。
