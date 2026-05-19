# Qlib 默认实现与数据准备方案

## 为什么改成 Qlib

当前项目要从“轻量自研数据 + 自研评测”改成“Qlib 数据 + Qlib 评测”。这样可以减少大量市场细节工作，把团队精力集中在：

- 自然语言解析
- DSL 与策略编译
- Qlib target-weight adapter
- UI 演示与解释

第一版默认：

> `QlibDataProvider + QlibTargetWeightStrategy + QlibEvaluator`

## Qlib 数据初始化

开发者需要先准备 Qlib 格式数据目录。默认配置：

```python
provider_uri = "~/.qlib/qlib_data/cn_data"
region = "cn"
benchmark = "SH000300"
```

初始化流程建议封装在 `src/qlib_provider.py`：

```python
import qlib
from qlib.constant import REG_CN

def init_qlib(provider_uri: str) -> None:
    qlib.init(provider_uri=provider_uri, region=REG_CN)
```

注意：
- `provider_uri` 必须和 `region` 匹配。
- 不要在 Qlib 源码仓库目录中运行项目，避免 import 冲突。
- Qlib 官方示例数据来自公开数据源，可能不完美；答辩时要说明这是 demo 数据口径。

## QlibDataProvider 的职责

1. 初始化 Qlib。
2. 读取交易日历。
3. 解析 Qlib 内置股票池或用户股票列表。
4. 读取日频行情字段。
5. 做 symbol 标准化。
6. 输出本项目统一 `BarsFrame` / `CalendarFrame`。
7. 暴露 capability summary。

Provider 不负责：
- 指标计算
- 策略逻辑
- 权重构建
- Qlib 回测调用
- UI 展示

## 推荐读取接口

### 1. 交易日历

使用 Qlib `D.calendar(...)`，封装为：

```python
get_calendar(start, end) -> CalendarFrame
```

### 2. 股票池

支持两类输入：

- Qlib 内置市场名：`csi300`、`csi500` 等
- 用户输入股票列表：`SH600036,SZ000001`

Qlib 风格内部代码：

```text
SH600036
SZ000001
SH000300
```

UI 可接受旧格式：

```text
600036.SH
000001.SZ
```

但进入 DSL 和 DataProvider 前必须转成 Qlib 风格。

### 3. 行情字段

V1 推荐字段：

```python
fields = ["$open", "$high", "$low", "$close", "$volume"]
```

如策略需要均线、收益率等指标，优先在本项目 `indicators.py` 中基于这些字段计算。后续可以扩展为直接使用 Qlib ExpressionOps，但 V1 不把 DSL 直接绑定到 Qlib 表达式。

## 数据目录与缓存边界

Qlib 自身会管理数据目录和缓存。本项目 V1 不再设计独立的 `LocalCacheStore`。

项目只保留三类轻量文件：

```text
sample_data/
├── demo_symbols.csv
├── demo_pool_csi300_small.csv
└── README.md
```

这些文件只用于：
- 本地 smoke test
- UI 默认示例
- 当完整 Qlib 数据不可用时给出清晰错误

## 推荐的数据准备说明

在 `scripts/prepare_qlib_data.md` 或项目 README 中写明：

```bash
python scripts/get_data.py qlib_data --target_dir ~/.qlib/qlib_data/cn_data --region cn
```

如果团队使用已有 Qlib 数据目录，只需要在 `.env` 中配置：

```text
QLIB_PROVIDER_URI=~/.qlib/qlib_data/cn_data
QLIB_REGION=cn
QLIB_BENCHMARK=SH000300
```

## 第一版推荐开发数据范围

为了让 5 人并行开发更稳，先固定：

- benchmark：`SH000300`
- 单股样本：`SH600036`、`SZ000001`、`SH600519`
- 预置池：`csi300`
- UI 小池：从 `csi300` 取 20~50 只作为 demo pool
- 回测区间：`2021-01-01` 到 `2024-12-31`

## 风险与说明

- Qlib 数据可能缺少某些真实交易限制字段，必须通过 capability summary 展示。
- Qlib 官方 CN region 已内置 A 股交易单位和涨跌停阈值等默认配置，但项目仍应在结果页展示实际启用的 `exchange_kwargs`。
- 如果某台机器没有 Qlib 数据，不要让 UI 静默失败；应显示数据目录缺失和准备命令。

## 官方参考

- Qlib Initialization: https://qlib.readthedocs.io/en/latest/start/initialization.html
- Qlib Data Framework & Usage: https://qlib.readthedocs.io/en/latest/component/data.html
- Qlib Data Retrieval examples: https://qlib.readthedocs.io/en/v0.7.2/start/getdata.html
