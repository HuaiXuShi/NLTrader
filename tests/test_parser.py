import json

import pytest

from src.compiler import compile_strategy
from src.config import Settings
from src.dsl import validate_dsl
from src.parser import StrategyParser, parse_strategy, parse_result_from_text


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


def test_parse_result_from_text_strips_code_fences_and_unwraps_dsl():
    raw = """```json
{
  "strategy_kind": "timeseries",
  "market": "CN_A",
  "frequency": "D",
  "universe": {"type": "single_symbol", "symbols": ["600036.SH"]},
  "rebalance": {"freq": "daily"},
  "signal": {
    "entry_rules": [
      {
        "lhs": {"indicator": "SMA", "params": [5]},
        "op": "cross_above",
        "rhs": {"indicator": "SMA", "params": [20]}
      }
    ],
    "exit_rules": []
  }
}
```"""

    result = parse_result_from_text(raw)

    assert result.strategy_kind == "timeseries"
    assert result.dsl["universe"]["symbols"] == ["SH600036"]
    assert result.parse_confidence == 0.4


def test_parse_result_from_text_rejects_unknown_fields_before_compiler():
    raw = {
        "dsl": {
            "strategy_kind": "timeseries",
            "market": "CN_A",
            "frequency": "D",
            "universe": {"type": "single_symbol", "symbols": ["SH600036"]},
            "rebalance": {"freq": "daily"},
            "signal": {
                "entry_rules": [
                    {
                        "lhs": {"indicator": "CLOSE"},
                        "op": ">",
                        "rhs": {"value": 0},
                        "qlib_expr": "$close > Ref($close, 1)",
                    }
                ],
                "exit_rules": [],
            },
        },
        "strategy_kind": "timeseries",
        "assumptions": [],
        "warnings": [],
        "human_summary": "",
        "parse_confidence": 0.9,
        "python": "print('do not run')",
    }

    with pytest.raises(ValueError, match="unknown ParseResult fields"):
        parse_result_from_text(json.dumps(raw))


def test_parse_result_from_text_rejects_unknown_dsl_fields_before_compiler():
    raw = {
        "dsl": {
            "strategy_kind": "timeseries",
            "market": "CN_A",
            "frequency": "D",
            "universe": {"type": "single_symbol", "symbols": ["SH600036"]},
            "rebalance": {"freq": "daily"},
            "signal": {
                "entry_rules": [
                    {
                        "lhs": {"indicator": "CLOSE"},
                        "op": ">",
                        "rhs": {"value": 0},
                        "qlib_expr": "$close > Ref($close, 1)",
                    }
                ],
                "exit_rules": [],
            },
        },
        "strategy_kind": "timeseries",
        "assumptions": [],
        "warnings": [],
        "human_summary": "",
        "parse_confidence": 0.9,
    }

    with pytest.raises(ValueError, match="unknown dsl.signal.entry_rules"):
        parse_result_from_text(json.dumps(raw))


@pytest.mark.parametrize(
    "value",
    [
        "$close > Ref($close, 1)",
        "__import__('os').system('echo unsafe')",
    ],
)
def test_parse_result_from_text_rejects_string_expression_values(value):
    raw = {
        "dsl": {
            "strategy_kind": "timeseries",
            "market": "CN_A",
            "frequency": "D",
            "universe": {"type": "single_symbol", "symbols": ["SH600036"]},
            "rebalance": {"freq": "daily"},
            "signal": {
                "entry_rules": [
                    {
                        "lhs": {"indicator": "CLOSE"},
                        "op": ">",
                        "rhs": {"value": value},
                    }
                ],
                "exit_rules": [],
            },
        },
        "strategy_kind": "timeseries",
        "assumptions": [],
        "warnings": [],
        "human_summary": "",
        "parse_confidence": 0.9,
    }

    with pytest.raises(ValueError, match="expression value"):
        parse_result_from_text(json.dumps(raw))


def test_parse_result_from_text_rejects_rule_expression_string_params_before_compiler():
    raw = {
        "dsl": {
            "strategy_kind": "timeseries",
            "market": "CN_A",
            "frequency": "D",
            "universe": {"type": "single_symbol", "symbols": ["SH600036"]},
            "rebalance": {"freq": "daily"},
            "signal": {
                "entry_rules": [
                    {
                        "lhs": {
                            "indicator": "SMA",
                            "params": ["$close > Ref($close, 1)"],
                        },
                        "op": ">",
                        "rhs": {"value": 0},
                    }
                ],
                "exit_rules": [],
            },
        },
        "strategy_kind": "timeseries",
        "assumptions": [],
        "warnings": [],
        "human_summary": "",
        "parse_confidence": 0.9,
    }

    with pytest.raises(ValueError, match="params"):
        parse_result_from_text(json.dumps(raw))


def test_parse_result_from_text_rejects_score_indicator_alias():
    raw = {
        "dsl": {
            "strategy_kind": "cross_sectional",
            "market": "CN_A",
            "frequency": "D",
            "universe": {"type": "symbol_list", "symbols": ["SH600036", "SZ000001"]},
            "rebalance": {"freq": "monthly"},
            "selection": {
                "filters": [],
                "score": {"indicator": "RETURN_N", "params": [20]},
                "rank_order": "desc",
                "top_n": 1,
            },
            "construction": {"weighting": "equal_weight"},
        },
        "strategy_kind": "cross_sectional",
        "assumptions": [],
        "warnings": [],
        "human_summary": "",
        "parse_confidence": 0.9,
    }

    with pytest.raises(ValueError, match="unknown dsl.selection.score fields"):
        parse_result_from_text(json.dumps(raw))


def test_parse_result_from_text_rejects_score_dict_params_repair():
    raw = {
        "dsl": {
            "strategy_kind": "cross_sectional",
            "market": "CN_A",
            "frequency": "D",
            "universe": {"type": "symbol_list", "symbols": ["SH600036", "SZ000001"]},
            "rebalance": {"freq": "monthly"},
            "selection": {
                "filters": [],
                "score": {"factor": "RETURN_N", "params": {"n": 20}},
                "rank_order": "desc",
                "top_n": 1,
            },
            "construction": {"weighting": "equal_weight"},
        },
        "strategy_kind": "cross_sectional",
        "assumptions": [],
        "warnings": [],
        "human_summary": "",
        "parse_confidence": 0.9,
    }

    with pytest.raises(ValueError, match="score.params"):
        parse_result_from_text(json.dumps(raw))


def test_unsupported_minute_strategy_is_rejected_without_compilable_dsl():
    result = parse_strategy("招商银行5分钟均线上穿20分钟均线买入。", fallback=False)

    assert result.dsl == {}
    assert result.strategy_kind == "unsupported"
    assert result.parse_confidence < 0.5
    assert any("分钟" in warning or "minute" in warning.lower() for warning in result.warnings)
    with pytest.raises(Exception):
        compile_strategy(result.dsl)


def test_limited_fallback_emits_explicit_warning_when_api_settings_missing():
    parser = StrategyParser(
        Settings(llm_api_base=None, llm_api_key=None, llm_model=None),
    )

    result = parser.parse("招商银行600036，5日均线上穿20日均线买入，跌破10日均线卖出。")

    assert result.strategy_kind == "timeseries"
    assert any("fallback" in warning.lower() for warning in result.warnings)
    assert validate_dsl(result.dsl)["universe"]["symbols"] == ["SH600036"]


def test_limited_fallback_does_not_fabricate_ma_for_unrelated_supported_text():
    parser = StrategyParser(
        Settings(llm_api_base=None, llm_api_key=None, llm_model=None),
    )

    result = parser.parse("招商银行600036，RSI低于30买入，高于70卖出。")

    assert result.dsl == {}
    assert result.strategy_kind == "unsupported"
    assert any("fallback" in warning.lower() for warning in result.warnings)
