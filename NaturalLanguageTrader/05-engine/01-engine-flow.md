# Qlib 评测内核流程

## 核心思想

内核不关心策略来自：
- 自然语言
- 手写 DSL
- 示例模板

它只关心两件事：

1. 当前市场状态
2. 当日目标权重

## 日频主流程

```text
初始化 Qlib
  ↓
加载 calendar / benchmark / universe
  ↓
对每个交易日推进
  ↓
准备 market_state（当前及历史窗口）
  ↓
调用 compiled_strategy.generate_target_weights(...)
  ↓
QlibTargetWeightStrategy 生成目标仓位
  ↓
Qlib 根据目标仓位生成订单
  ↓
Qlib executor / exchange 按配置撮合
  ↓
Qlib 生成 report_normal / positions_normal
  ↓
QlibEvaluator 计算 risk_analysis 并转换 BacktestResult
```

## MarketState 建议包含

- 当前日期
- 历史价格窗口
- 当前 universe 内可用标的列表
- capability summary
- benchmark 序列（若有）

## PortfolioState 建议包含

- 当前现金
- 当前持仓数量
- 当前市值
- 每个仓位的持有天数
- 上次买入日期（用于 T+1）

## 目标权重与订单生成

### 目标权重示例
单股时序：
```json
{"SH600036": 1.0}
```

横截面：
```json
{"SH600036": 0.25, "SH600519": 0.25, "SZ000001": 0.25, "SZ000858": 0.25}
```

### 订单生成逻辑
V1 不在本项目里重复实现订单生成。  
`QlibTargetWeightStrategy` 输出目标仓位后，交给 Qlib target-weight 策略基类或等价接口生成订单。

## 第一版关于股数与 lot 的建议

Qlib CN region 默认包含 A 股交易单位设置。项目不再自研 lot 取整，但必须在 capability summary 中显示实际使用的 region 和 exchange 参数。

## 时序与横截面如何统一

### 时序
策略在每个交易日判断“是否持有该股票”，本质是产生一个 0 或 1 的目标权重。

### 横截面
策略在调仓点对股票池打分、排序、选股并分配等权，产生一组目标权重。

这两种情况对 Qlib adapter 来说没有本质区别。

## 引擎第一版输出内容

建议至少记录并转换：

- `equity_curve`
- `positions_history`
- `trades`
- `rebalances`
- `metrics`
- `warnings`
- `capability_summary`
- `qlib_report`
- `qlib_positions`
- `qlib_analysis`
