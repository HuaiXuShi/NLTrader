import os

import pytest

from src.dsl import validate_dsl
from src.parser import parse_strategy


pytestmark = pytest.mark.skipif(
    not os.getenv("RUN_REAL_LLM_TESTS"),
    reason="real LLM integration tests require RUN_REAL_LLM_TESTS=1",
)


def test_real_llm_parses_single_stock_ma_strategy_into_timeseries():
    result = parse_strategy(
        "针对招商银行600036，5日均线上穿20日均线买入，跌破10日均线卖出。",
        fallback=False,
    )

    assert result.strategy_kind == "timeseries"
    assert result.parse_confidence >= 0.5
    validated = validate_dsl(result.dsl)
    assert validated["strategy_kind"] == "timeseries"
    assert validated["universe"]["symbols"] == ["SH600036"]
    rules = validated["signal"]["entry_rules"] + validated["signal"]["exit_rules"]
    assert any(rule["lhs"].get("indicator") == "SMA" for rule in rules)
    assert any(rule["op"] in {"cross_above", ">"} for rule in rules)


def test_real_llm_parses_monthly_momentum_top_n_stock_pool():
    result = parse_strategy(
        "每月调仓，在股票池600036、000001、600519、000858、300750、002415、601318、601888、"
        "600030、601166、000333、600900中选择过去20日涨幅最高的10只股票等权持有。",
        fallback=False,
    )

    assert result.strategy_kind == "cross_sectional"
    validated = validate_dsl(result.dsl)
    assert validated["strategy_kind"] == "cross_sectional"
    assert validated["rebalance"]["freq"] == "monthly"
    assert validated["selection"]["score"]["factor"] == "RETURN_N"
    assert validated["selection"]["score"].get("params") == [20]
    assert validated["selection"]["top_n"] == 10
    assert validated["construction"]["weighting"] == "equal_weight"
    assert {"SH600036", "SZ000001", "SH600519"} <= set(
        validated["universe"]["symbols"]
    )
