import pytest

from src.dsl import (
    SUPPORTED_INDICATORS,
    ValidationError,
    validate_dsl,
    validate_target_weights,
)


def test_supported_indicators_include_close_for_rule_validation():
    assert "CLOSE" in SUPPORTED_INDICATORS


def test_validate_timeseries_dsl_accepts_supported_entry_and_exit_rules():
    dsl = {
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
                    "rhs": {"indicator": "SMA", "params": [20]},
                }
            ],
            "exit_rules": [
                {
                    "lhs": {"indicator": "CLOSE"},
                    "op": "<",
                    "rhs": {"indicator": "SMA", "params": [10]},
                }
            ],
        },
    }

    validated = validate_dsl(dsl)

    assert validated["universe"]["symbols"] == ["SH600036"]


def test_validate_cross_sectional_dsl_accepts_supported_selection():
    dsl = {
        "strategy_kind": "cross_sectional",
        "market": "CN_A",
        "frequency": "D",
        "universe": {
            "type": "symbol_list",
            "symbols": ["SH600036", "000001.SZ"],
        },
        "rebalance": {"freq": "monthly"},
        "selection": {
            "filters": [
                {
                    "lhs": {"indicator": "VOL_MA_RATIO", "params": [20]},
                    "op": ">",
                    "rhs": {"value": 1.2},
                }
            ],
            "score": {"factor": "RETURN_N", "params": [20]},
            "rank_order": "desc",
            "top_n": 2,
        },
        "construction": {"weighting": "equal_weight"},
    }

    validated = validate_dsl(dsl)

    assert validated["universe"]["symbols"] == ["SH600036", "SZ000001"]


def test_validate_cross_sectional_dsl_accepts_sma_gap_score_factor():
    dsl = {
        "strategy_kind": "cross_sectional",
        "market": "CN_A",
        "frequency": "D",
        "universe": {"type": "preset_pool", "pool_name": "CSI300"},
        "rebalance": {"freq": "monthly"},
        "selection": {
            "score": {"factor": "SMA_GAP", "params": [5, 20]},
            "rank_order": "desc",
            "top_n": 10,
        },
        "construction": {"weighting": "equal_weight"},
    }

    validated = validate_dsl(dsl)

    assert validated["selection"]["score"]["factor"] == "SMA_GAP"


def test_validate_dsl_accepts_risk_stop_loss_ratio_and_normalizes_to_float():
    dsl = {
        "strategy_kind": "timeseries",
        "market": "CN_A",
        "frequency": "D",
        "universe": {"type": "single_symbol", "symbols": ["600036.SH"]},
        "rebalance": {"freq": "daily"},
        "risk": {"stop_loss": 0.08},
        "signal": {
            "entry_rules": [
                {
                    "lhs": {"indicator": "SMA", "params": [5]},
                    "op": ">",
                    "rhs": {"value": 1},
                }
            ],
            "exit_rules": [],
        },
    }

    validated = validate_dsl(dsl)

    assert validated["risk"]["stop_loss"] == 0.08
    assert isinstance(validated["risk"]["stop_loss"], float)


@pytest.mark.parametrize(
    ("stop_loss", "message"),
    [
        ({"type": "percent", "value": 8}, "risk.stop_loss must be a numeric ratio"),
        ("8%", "risk.stop_loss must be a numeric ratio"),
        (True, "risk.stop_loss must be a numeric ratio"),
        (-0.08, "risk.stop_loss must be between 0 and 1"),
        (8, "risk.stop_loss must be between 0 and 1"),
        (1, "risk.stop_loss must be between 0 and 1"),
    ],
)
def test_validate_dsl_rejects_invalid_risk_stop_loss_values(stop_loss, message):
    with pytest.raises(ValidationError, match=message):
        validate_dsl(
            {
                "strategy_kind": "timeseries",
                "market": "CN_A",
                "frequency": "D",
                "universe": {"type": "single_symbol", "symbols": ["600036.SH"]},
                "rebalance": {"freq": "daily"},
                "risk": {"stop_loss": stop_loss},
                "signal": {
                    "entry_rules": [
                        {
                            "lhs": {"indicator": "SMA", "params": [5]},
                            "op": ">",
                            "rhs": {"value": 1},
                        }
                    ],
                    "exit_rules": [],
                },
            }
        )


def test_validate_dsl_rejects_unknown_risk_fields():
    with pytest.raises(ValidationError, match=r"unsupported risk fields: \['max_drawdown'\]"):
        validate_dsl(
            {
                "strategy_kind": "timeseries",
                "market": "CN_A",
                "frequency": "D",
                "universe": {"type": "single_symbol", "symbols": ["600036.SH"]},
                "rebalance": {"freq": "daily"},
                "risk": {"max_drawdown": 0.1},
                "signal": {
                    "entry_rules": [
                        {
                            "lhs": {"indicator": "SMA", "params": [5]},
                            "op": ">",
                            "rhs": {"value": 1},
                        }
                    ],
                    "exit_rules": [],
                },
            }
        )


@pytest.mark.parametrize(
    "patch",
    [
        {"strategy_kind": "intraday"},
        {"market": "US"},
        {"frequency": "1min"},
        {"rebalance": {"freq": "quarterly"}},
    ],
)
def test_validate_dsl_rejects_unsupported_top_level_values(patch):
    dsl = {
        "strategy_kind": "timeseries",
        "market": "CN_A",
        "frequency": "D",
        "universe": {"type": "single_symbol", "symbols": ["SH600036"]},
        "rebalance": {"freq": "daily"},
        "signal": {
            "entry_rules": [
                {"lhs": {"indicator": "SMA", "params": [5]}, "op": ">", "rhs": {"value": 1}}
            ],
            "exit_rules": [],
        },
    }
    dsl.update(patch)

    with pytest.raises(ValidationError):
        validate_dsl(dsl)


def test_validate_timeseries_requires_entry_or_exit_rule():
    with pytest.raises(ValidationError, match="entry or exit"):
        validate_dsl(
            {
                "strategy_kind": "timeseries",
                "market": "CN_A",
                "frequency": "D",
                "universe": {"type": "single_symbol", "symbols": ["SH600036"]},
                "rebalance": {"freq": "daily"},
                "signal": {"entry_rules": [], "exit_rules": []},
            }
        )


def test_validate_timeseries_requires_universe():
    with pytest.raises(ValidationError, match="universe"):
        validate_dsl(
            {
                "strategy_kind": "timeseries",
                "market": "CN_A",
                "frequency": "D",
                "rebalance": {"freq": "daily"},
                "signal": {
                    "entry_rules": [
                        {
                            "lhs": {"indicator": "SMA", "params": [5]},
                            "op": ">",
                            "rhs": {"value": 1},
                        }
                    ],
                    "exit_rules": [],
                },
            }
        )


def test_validate_dsl_wraps_invalid_universe_symbol_as_validation_error():
    with pytest.raises(ValidationError, match="universe.*symbol"):
        validate_dsl(
            {
                "strategy_kind": "timeseries",
                "market": "CN_A",
                "frequency": "D",
                "universe": {"type": "single_symbol", "symbols": ["600036.SS"]},
                "rebalance": {"freq": "daily"},
                "signal": {
                    "entry_rules": [
                        {
                            "lhs": {"indicator": "SMA", "params": [5]},
                            "op": ">",
                            "rhs": {"value": 1},
                        }
                    ],
                    "exit_rules": [],
                },
            }
        )


def test_validate_cross_sectional_requires_universe():
    with pytest.raises(ValidationError, match="universe"):
        validate_dsl(
            {
                "strategy_kind": "cross_sectional",
                "market": "CN_A",
                "frequency": "D",
                "rebalance": {"freq": "monthly"},
                "selection": {"score": {"factor": "RETURN_N"}, "top_n": 3},
            }
        )


def test_validate_cross_sectional_requires_score():
    with pytest.raises(ValidationError, match="score"):
        validate_dsl(
            {
                "strategy_kind": "cross_sectional",
                "market": "CN_A",
                "frequency": "D",
                "universe": {"type": "preset_pool", "pool_name": "CSI300"},
                "rebalance": {"freq": "monthly"},
                "selection": {"top_n": 3},
                "construction": {"weighting": "equal_weight"},
            }
        )


def test_validate_cross_sectional_requires_top_or_bottom_n():
    with pytest.raises(ValidationError, match="top_n or bottom_n"):
        validate_dsl(
            {
                "strategy_kind": "cross_sectional",
                "market": "CN_A",
                "frequency": "D",
                "universe": {"type": "preset_pool", "pool_name": "CSI300"},
                "rebalance": {"freq": "monthly"},
                "selection": {"score": {"factor": "RETURN_N", "params": [20]}},
                "construction": {"weighting": "equal_weight"},
            }
        )


def test_validate_cross_sectional_rejects_both_top_n_and_bottom_n():
    with pytest.raises(ValidationError, match="top_n or bottom_n"):
        validate_dsl(
            {
                "strategy_kind": "cross_sectional",
                "market": "CN_A",
                "frequency": "D",
                "universe": {"type": "preset_pool", "pool_name": "CSI300"},
                "rebalance": {"freq": "monthly"},
                "selection": {
                    "score": {"factor": "RETURN_N", "params": [20]},
                    "rank_order": "desc",
                    "top_n": 3,
                    "bottom_n": 3,
                },
                "construction": {"weighting": "equal_weight"},
            }
        )


@pytest.mark.parametrize("field", ["top_n", "bottom_n"])
def test_validate_cross_sectional_requires_positive_top_or_bottom_n(field):
    with pytest.raises(ValidationError, match=field):
        validate_dsl(
            {
                "strategy_kind": "cross_sectional",
                "market": "CN_A",
                "frequency": "D",
                "universe": {"type": "preset_pool", "pool_name": "CSI300"},
                "rebalance": {"freq": "weekly"},
                "selection": {
                    "score": {"factor": "RETURN_N", "params": [20]},
                    field: 0,
                },
                "construction": {"weighting": "equal_weight"},
            }
        )


def test_validate_cross_sectional_rejects_unsupported_rank_order():
    with pytest.raises(ValidationError, match="rank_order"):
        validate_dsl(
            {
                "strategy_kind": "cross_sectional",
                "market": "CN_A",
                "frequency": "D",
                "universe": {"type": "preset_pool", "pool_name": "CSI300"},
                "rebalance": {"freq": "monthly"},
                "selection": {
                    "score": {"factor": "RETURN_N", "params": [20]},
                    "rank_order": "sideways",
                    "top_n": 3,
                },
                "construction": {"weighting": "equal_weight"},
            }
        )


def test_validate_cross_sectional_requires_equal_weight_construction():
    with pytest.raises(ValidationError, match="construction"):
        validate_dsl(
            {
                "strategy_kind": "cross_sectional",
                "market": "CN_A",
                "frequency": "D",
                "universe": {"type": "preset_pool", "pool_name": "CSI300"},
                "rebalance": {"freq": "monthly"},
                "selection": {
                    "score": {"factor": "RETURN_N", "params": [20]},
                    "top_n": 3,
                },
            }
        )


def test_validate_cross_sectional_rejects_unsupported_construction_weighting():
    with pytest.raises(ValidationError, match="weighting"):
        validate_dsl(
            {
                "strategy_kind": "cross_sectional",
                "market": "CN_A",
                "frequency": "D",
                "universe": {"type": "preset_pool", "pool_name": "CSI300"},
                "rebalance": {"freq": "monthly"},
                "selection": {
                    "score": {"factor": "RETURN_N", "params": [20]},
                    "top_n": 3,
                },
                "construction": {"weighting": "cap_weight"},
            }
        )


def test_validate_dsl_rejects_unknown_indicator():
    with pytest.raises(ValidationError, match="indicator"):
        validate_dsl(
            {
                "strategy_kind": "timeseries",
                "market": "CN_A",
                "frequency": "D",
                "universe": {"type": "single_symbol", "symbols": ["SH600036"]},
                "rebalance": {"freq": "daily"},
                "signal": {
                    "entry_rules": [
                        {
                            "lhs": {"indicator": "SMA_GAP", "params": [5, 20]},
                            "op": ">",
                            "rhs": {"value": 0},
                        }
                    ],
                    "exit_rules": [],
                },
            }
        )


def test_validate_dsl_rejects_unknown_operator():
    with pytest.raises(ValidationError, match="operator"):
        validate_dsl(
            {
                "strategy_kind": "timeseries",
                "market": "CN_A",
                "frequency": "D",
                "universe": {"type": "single_symbol", "symbols": ["SH600036"]},
                "rebalance": {"freq": "daily"},
                "signal": {
                    "entry_rules": [
                        {
                            "lhs": {"indicator": "SMA", "params": [5]},
                            "op": "crosses",
                            "rhs": {"indicator": "SMA", "params": [20]},
                        }
                    ],
                    "exit_rules": [],
                },
            }
        )


@pytest.mark.parametrize(
    "params",
    [
        ["$close > Ref($close, 1)"],
        [True],
        [{"window": 5}],
        [[5]],
    ],
)
def test_validate_dsl_rejects_unsafe_indicator_params(params):
    with pytest.raises(ValidationError, match="params"):
        validate_dsl(
            {
                "strategy_kind": "timeseries",
                "market": "CN_A",
                "frequency": "D",
                "universe": {"type": "single_symbol", "symbols": ["SH600036"]},
                "rebalance": {"freq": "daily"},
                "signal": {
                    "entry_rules": [
                        {
                            "lhs": {"indicator": "SMA", "params": params},
                            "op": ">",
                            "rhs": {"value": 0},
                        }
                    ],
                    "exit_rules": [],
                },
            }
        )


@pytest.mark.parametrize(
    "params",
    [
        ["$close > Ref($close, 1)"],
        [False],
        [{"window": 20}],
        [[20]],
    ],
)
def test_validate_dsl_rejects_unsafe_score_factor_params(params):
    with pytest.raises(ValidationError, match="params"):
        validate_dsl(
            {
                "strategy_kind": "cross_sectional",
                "market": "CN_A",
                "frequency": "D",
                "universe": {"type": "preset_pool", "pool_name": "CSI300"},
                "rebalance": {"freq": "monthly"},
                "selection": {
                    "score": {"factor": "RETURN_N", "params": params},
                    "rank_order": "desc",
                    "top_n": 3,
                },
                "construction": {"weighting": "equal_weight"},
            }
        )


@pytest.mark.parametrize(
    ("indicator", "params"),
    [
        ("CLOSE", [1]),
        ("SMA", []),
        ("SMA", [0]),
        ("SMA", [5, 20]),
        ("MACD", [12]),
        ("MACD", [12, 26, 0]),
        ("BOLL_UPPER", []),
        ("BOLL_LOWER", [20, 2]),
    ],
)
def test_validate_dsl_rejects_invalid_indicator_param_arity(indicator, params):
    with pytest.raises(ValidationError, match="params"):
        validate_dsl(
            {
                "strategy_kind": "timeseries",
                "market": "CN_A",
                "frequency": "D",
                "universe": {"type": "single_symbol", "symbols": ["SH600036"]},
                "rebalance": {"freq": "daily"},
                "signal": {
                    "entry_rules": [
                        {
                            "lhs": {"indicator": indicator, "params": params},
                            "op": ">",
                            "rhs": {"value": 0},
                        }
                    ],
                    "exit_rules": [],
                },
            }
        )


@pytest.mark.parametrize(
    ("factor", "params"),
    [
        ("RETURN_N", []),
        ("RETURN_N", [0]),
        ("RETURN_N", [20, 5]),
        ("SMA_GAP", [5]),
        ("SMA_GAP", [5, 0]),
        ("SMA_GAP", [5, 20, 60]),
    ],
)
def test_validate_dsl_rejects_invalid_score_factor_param_arity(factor, params):
    with pytest.raises(ValidationError, match="params"):
        validate_dsl(
            {
                "strategy_kind": "cross_sectional",
                "market": "CN_A",
                "frequency": "D",
                "universe": {"type": "preset_pool", "pool_name": "CSI300"},
                "rebalance": {"freq": "monthly"},
                "selection": {
                    "score": {"factor": factor, "params": params},
                    "rank_order": "desc",
                    "top_n": 3,
                },
                "construction": {"weighting": "equal_weight"},
            }
        )


@pytest.mark.parametrize(
    "weights",
    [
        {"SH600036": 0.4, "SZ000001": 0.6},
        {"600036.SH": 1.0},
        {},
    ],
)
def test_validate_target_weights_accepts_long_only_sum_at_most_one(weights):
    validated = validate_target_weights(weights)

    assert sum(validated.values()) <= 1


@pytest.mark.parametrize(
    "weights",
    [
        {"SH600036": -0.1},
        {"SH600036": 0.7, "SZ000001": 0.4},
    ],
)
def test_validate_target_weights_rejects_short_or_overallocated_weights(weights):
    with pytest.raises(ValidationError):
        validate_target_weights(weights)


def test_validate_target_weights_wraps_invalid_symbol_as_validation_error():
    with pytest.raises(ValidationError, match="target weight symbol"):
        validate_target_weights({"600036.SS": 1.0})
