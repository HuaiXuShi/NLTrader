# 示例策略

这份文件用于：
- parser prompt 参考
- compiler 测试参考
- demo 样例库

---

## 1. 单股：均线交叉 + 放量

### 自然语言
5日均线上穿20日均线且成交量大于20日均量1.5倍时买入，跌破10日均线或亏损8%卖出。

### 预期类型
`timeseries`

### 关键 assumptions
- 无需额外 assumptions，只有成交量倍数参数明确

---

## 2. 单股：突破 60 日高点

### 自然语言
股价突破过去60日最高收盘价时买入，跌破20日均线卖出。

### 预期类型
`timeseries`

### 关键原语
- `breakout_high`
- `SMA(20)`

---

## 3. 单股：RSI 反转

### 自然语言
RSI 低于 30 时买入，RSI 高于 70 时卖出。

### 预期类型
`timeseries`

### 关键 assumptions
- RSI 默认周期设为 14

---

## 4. 单股：模糊表达示例

### 自然语言
放量上涨的时候跟进去，趋势破了就出来。

### 预期类型
`timeseries`

### 预期 assumptions
- “放量”=`VOL_MA_RATIO(20) > 1.5`
- “上涨”=`close > previous_close`
- “趋势破了”=`close < SMA(20)`（只是默认解释）

### 预期 warnings
- 原始表述较模糊，已使用默认映射

---

## 5. 横截面：月度动量 top N

### 自然语言
每月调仓，在股票池中选择过去20日涨幅最高的10只股票等权持有。

### 预期类型
`cross_sectional`

### 关键原语
- `rebalance = monthly`
- `score = RETURN_N(20)`
- `rank_order = desc`
- `top_n = 10`
- `equal_weight`

---

## 6. 横截面：先过滤再排序

### 自然语言
每月调仓，在股票池中先剔除最近20日平均成交量太低的股票，再选过去60日涨幅最高的5只等权持有。

### 预期类型
`cross_sectional`

### 关键 assumptions
- “成交量太低”需要默认阈值或要求用户补充
- 推荐 parser 给出 warning

---

## 7. 横截面：低 RSI 反转

### 自然语言
在股票池中选 RSI 最低的 10 只股票，每周调仓，等权持有。

### 预期类型
`cross_sectional`

### 关键 assumptions
- RSI 周期默认 14

---

## 8. 不支持示例：分钟级

### 自然语言
5分钟均线上穿20分钟均线买入。

### 预期结果
拒绝执行，返回 unsupported。

---

## 9. 不支持示例：公告驱动

### 自然语言
公司发布回购公告后买入，持有20天。

### 预期结果
拒绝执行，返回 unsupported。

---

## 10. 需要补充信息示例：横截面但没给股票池

### 自然语言
每个月选过去20日涨幅最高的10只股票等权持有。

### 预期结果
返回 warning 或 error，提示缺少 universe。
