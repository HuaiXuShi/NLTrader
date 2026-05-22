import pytest
import pandas as pd

from src.compiler import compile_strategy
from src.dsl import ValidationError
from src.models import MarketState, PortfolioState


def _market_state(date, rows):
    return MarketState(date=date, bars=pd.DataFrame(rows))


def _timeseries_dsl(entry_rules, exit_rules=None, risk=None):
    return {
        "strategy_kind": "timeseries",
        "market": "CN_A",
        "frequency": "D",
        "universe": {"type": "single_symbol", "symbols": ["SH600036"]},
        "rebalance": {"freq": "daily"},
        "signal": {
            "entry_rules": entry_rules,
            "exit_rules": exit_rules or [],
        },
        "risk": risk or {},
    }


def test_timeseries_cross_above_entry_returns_full_weight_without_lookahead():
    rows = [
        {
            "date": "2021-01-01",
            "symbol": "SH600036",
            "open": 1,
            "high": 1,
            "low": 1,
            "close": 1,
            "volume": 100,
        },
        {
            "date": "2021-01-02",
            "symbol": "SH600036",
            "open": 1,
            "high": 1,
            "low": 1,
            "close": 1,
            "volume": 100,
        },
        {
            "date": "2021-01-03",
            "symbol": "SH600036",
            "open": 2,
            "high": 2,
            "low": 2,
            "close": 2,
            "volume": 100,
        },
        {
            "date": "2021-01-04",
            "symbol": "SH600036",
            "open": 100,
            "high": 100,
            "low": 100,
            "close": 100,
            "volume": 100,
        },
    ]
    dsl = _timeseries_dsl(
        [
            {
                "lhs": {"indicator": "SMA", "params": [1]},
                "op": "cross_above",
                "rhs": {"indicator": "SMA", "params": [2]},
            }
        ]
    )
    strategy = compile_strategy(dsl)

    weights = strategy.generate_target_weights(
        "2021-01-03",
        _market_state("2021-01-03", rows),
        PortfolioState(),
    )

    assert weights == {"SH600036": 1.0}


def test_timeseries_exit_rule_returns_empty_when_holding_and_close_below_sma():
    rows = [
        {
            "date": "2021-01-01",
            "symbol": "SH600036",
            "open": 10,
            "high": 10,
            "low": 10,
            "close": 10,
            "volume": 100,
        },
        {
            "date": "2021-01-02",
            "symbol": "SH600036",
            "open": 10,
            "high": 10,
            "low": 10,
            "close": 10,
            "volume": 100,
        },
        {
            "date": "2021-01-03",
            "symbol": "SH600036",
            "open": 5,
            "high": 5,
            "low": 5,
            "close": 5,
            "volume": 100,
        },
    ]
    dsl = _timeseries_dsl(
        [{"lhs": {"indicator": "CLOSE"}, "op": ">", "rhs": {"value": 0}}],
        [{"lhs": {"indicator": "CLOSE"}, "op": "<", "rhs": {"indicator": "SMA", "params": [2]}}],
    )
    strategy = compile_strategy(dsl)

    weights = strategy.generate_target_weights(
        "2021-01-03",
        _market_state("2021-01-03", rows),
        PortfolioState(weights={"SH600036": 1.0}),
    )

    assert weights == {}


def test_timeseries_stop_loss_exits_when_current_close_breaches_entry_price():
    rows = [
        {
            "date": "2021-01-01",
            "symbol": "SH600036",
            "open": 10,
            "high": 10,
            "low": 10,
            "close": 10,
            "volume": 100,
        },
        {
            "date": "2021-01-02",
            "symbol": "SH600036",
            "open": 9,
            "high": 9,
            "low": 9,
            "close": 9,
            "volume": 100,
        },
    ]
    dsl = _timeseries_dsl(
        [{"lhs": {"indicator": "CLOSE"}, "op": ">", "rhs": {"value": 0}}],
        risk={"stop_loss": 0.08},
    )
    strategy = compile_strategy(dsl)

    weights = strategy.generate_target_weights(
        "2021-01-02",
        _market_state("2021-01-02", rows),
        PortfolioState(weights={"SH600036": 1.0}, entry_price={"SH600036": 10.0}),
    )

    assert weights == {}


def test_timeseries_stale_bars_do_not_create_new_entry_signal():
    dsl = _timeseries_dsl(
        [{"lhs": {"indicator": "CLOSE"}, "op": ">", "rhs": {"value": 0}}]
    )
    strategy = compile_strategy(dsl)

    weights = strategy.generate_target_weights(
        "2021-01-02",
        _market_state(
            "2021-01-02",
            [
                {
                    "date": "2021-01-01",
                    "symbol": "SH600036",
                    "open": 10,
                    "high": 10,
                    "low": 10,
                    "close": 10,
                    "volume": 100,
                }
            ],
        ),
        PortfolioState(),
    )

    assert weights == {}


def test_timeseries_stale_bars_keep_existing_position_without_exit_signal():
    dsl = _timeseries_dsl(
        [{"lhs": {"indicator": "CLOSE"}, "op": ">", "rhs": {"value": 0}}],
        [{"lhs": {"indicator": "CLOSE"}, "op": "<", "rhs": {"value": 100}}],
    )
    strategy = compile_strategy(dsl)

    weights = strategy.generate_target_weights(
        "2021-01-02",
        _market_state(
            "2021-01-02",
            [
                {
                    "date": "2021-01-01",
                    "symbol": "SH600036",
                    "open": 10,
                    "high": 10,
                    "low": 10,
                    "close": 10,
                    "volume": 100,
                }
            ],
        ),
        PortfolioState(weights={"SH600036": 1.0}),
    )

    assert weights == {"SH600036": 1.0}


def test_cross_sectional_monthly_return_top_n_equal_weight():
    rows = []
    for symbol, start, end in [
        ("SH600036", 10, 13),
        ("SH600519", 10, 12),
        ("SZ000001", 10, 11),
    ]:
        for date, close in [
            ("2021-01-29", start),
            ("2021-02-26", end),
        ]:
            rows.append(
                {
                    "date": date,
                    "symbol": symbol,
                    "open": close,
                    "high": close,
                    "low": close,
                    "close": close,
                    "volume": 1000,
                }
            )
    dsl = {
        "strategy_kind": "cross_sectional",
        "market": "CN_A",
        "frequency": "D",
        "universe": {
            "type": "symbol_list",
            "symbols": ["SH600036", "SH600519", "SZ000001"],
        },
        "rebalance": {"freq": "daily"},
        "selection": {
            "filters": [],
            "score": {"factor": "RETURN_N", "params": [1]},
            "rank_order": "desc",
            "top_n": 2,
        },
        "construction": {"weighting": "equal_weight"},
    }
    strategy = compile_strategy(dsl)

    weights = strategy.generate_target_weights(
        "2021-02-26",
        _market_state("2021-02-26", rows),
        PortfolioState(),
    )

    assert weights == {"SH600036": 0.5, "SH600519": 0.5}


def test_cross_sectional_excludes_symbols_missing_requested_date_bars():
    rows = []
    for symbol, start, end_dates in [
        ("SH600036", 10, [("2021-01-29", 10), ("2021-02-26", 13)]),
        ("SH600519", 10, [("2021-01-29", 10), ("2021-02-25", 30)]),
        ("SZ000001", 10, [("2021-01-29", 10), ("2021-02-26", 12)]),
    ]:
        for date, close in end_dates:
            rows.append(
                {
                    "date": date,
                    "symbol": symbol,
                    "open": close,
                    "high": close,
                    "low": close,
                    "close": close,
                    "volume": 1000,
                }
            )
    dsl = {
        "strategy_kind": "cross_sectional",
        "market": "CN_A",
        "frequency": "D",
        "universe": {
            "type": "symbol_list",
            "symbols": ["SH600036", "SH600519", "SZ000001"],
        },
        "rebalance": {"freq": "daily"},
        "selection": {
            "filters": [],
            "score": {"factor": "RETURN_N", "params": [1]},
            "rank_order": "desc",
            "top_n": 2,
        },
        "construction": {"weighting": "equal_weight"},
    }
    strategy = compile_strategy(dsl)

    weights = strategy.generate_target_weights(
        "2021-02-26",
        _market_state("2021-02-26", rows),
        PortfolioState(),
    )

    assert weights == {"SH600036": 0.5, "SZ000001": 0.5}


def test_cross_sectional_monthly_rebalance_does_not_fire_without_requested_date_bars():
    dsl = {
        "strategy_kind": "cross_sectional",
        "market": "CN_A",
        "frequency": "D",
        "universe": {"type": "symbol_list", "symbols": ["SH600036", "SH600519"]},
        "rebalance": {"freq": "monthly"},
        "selection": {
            "filters": [],
            "score": {"factor": "RETURN_N", "params": [1]},
            "rank_order": "desc",
            "top_n": 1,
        },
        "construction": {"weighting": "equal_weight"},
    }
    strategy = compile_strategy(dsl)

    weights = strategy.generate_target_weights(
        "2021-02-01",
        _market_state(
            "2021-02-01",
            [
                {
                    "date": "2021-01-29",
                    "symbol": "SH600036",
                    "open": 10,
                    "high": 10,
                    "low": 10,
                    "close": 10,
                    "volume": 100,
                }
            ],
        ),
        PortfolioState(weights={"SH600519": 1.0}),
    )

    assert weights == {"SH600519": 1.0}


def test_cross_sectional_non_rebalance_day_keeps_existing_weights():
    dsl = {
        "strategy_kind": "cross_sectional",
        "market": "CN_A",
        "frequency": "D",
        "universe": {"type": "symbol_list", "symbols": ["SH600036", "SH600519"]},
        "rebalance": {"freq": "monthly"},
        "selection": {
            "filters": [],
            "score": {"factor": "RETURN_N", "params": [1]},
            "rank_order": "desc",
            "top_n": 1,
        },
        "construction": {"weighting": "equal_weight"},
    }
    strategy = compile_strategy(dsl)

    weights = strategy.generate_target_weights(
        "2021-02-25",
        _market_state("2021-02-25", []),
        PortfolioState(weights={"SH600036": 1.0}),
    )

    assert weights == {"SH600036": 1.0}


def test_cross_sectional_non_rebalance_day_does_not_fallback_to_internal_state():
    rows = []
    for symbol, start, end in [
        ("SH600036", 10, 13),
        ("SH600519", 10, 12),
    ]:
        for date, close in [
            ("2021-01-29", start),
            ("2021-02-26", end),
        ]:
            rows.append(
                {
                    "date": date,
                    "symbol": symbol,
                    "open": close,
                    "high": close,
                    "low": close,
                    "close": close,
                    "volume": 1000,
                }
            )
    dsl = {
        "strategy_kind": "cross_sectional",
        "market": "CN_A",
        "frequency": "D",
        "universe": {"type": "symbol_list", "symbols": ["SH600036", "SH600519"]},
        "rebalance": {"freq": "monthly"},
        "selection": {
            "filters": [],
            "score": {"factor": "RETURN_N", "params": [1]},
            "rank_order": "desc",
            "top_n": 1,
        },
        "construction": {"weighting": "equal_weight"},
    }
    strategy = compile_strategy(dsl)
    strategy.generate_target_weights(
        "2021-02-26",
        _market_state("2021-02-26", rows),
        PortfolioState(),
    )

    weights = strategy.generate_target_weights(
        "2021-02-27",
        _market_state(
            "2021-02-27",
            rows
            + [
                {
                    "date": "2021-02-27",
                    "symbol": "SH600036",
                    "open": 14,
                    "high": 14,
                    "low": 14,
                    "close": 14,
                    "volume": 1000,
                }
            ],
        ),
        PortfolioState(),
    )

    assert weights == {}


def test_cross_sectional_bottom_n_selects_lowest_raw_factor_values():
    rows = []
    for symbol, start, end in [
        ("SH600036", 10, 13),
        ("SH600519", 10, 12),
        ("SZ000001", 10, 11),
    ]:
        for date, close in [
            ("2021-01-29", start),
            ("2021-02-26", end),
        ]:
            rows.append(
                {
                    "date": date,
                    "symbol": symbol,
                    "open": close,
                    "high": close,
                    "low": close,
                    "close": close,
                    "volume": 1000,
                }
            )
    dsl = {
        "strategy_kind": "cross_sectional",
        "market": "CN_A",
        "frequency": "D",
        "universe": {
            "type": "symbol_list",
            "symbols": ["SH600036", "SH600519", "SZ000001"],
        },
        "rebalance": {"freq": "monthly"},
        "selection": {
            "filters": [],
            "score": {"factor": "RETURN_N", "params": [1]},
            "rank_order": "desc",
            "bottom_n": 2,
        },
        "construction": {"weighting": "equal_weight"},
    }
    strategy = compile_strategy(dsl)

    weights = strategy.generate_target_weights(
        "2021-02-26",
        _market_state("2021-02-26", rows),
        PortfolioState(),
    )

    assert weights == {"SZ000001": 0.5, "SH600519": 0.5}


def test_compiler_rejects_invalid_returned_target_weights():
    dsl = {
        "strategy_kind": "cross_sectional",
        "market": "CN_A",
        "frequency": "D",
        "universe": {"type": "symbol_list", "symbols": ["SH600036", "SH600519"]},
        "rebalance": {"freq": "monthly"},
        "selection": {
            "filters": [],
            "score": {"factor": "RETURN_N", "params": [1]},
            "rank_order": "desc",
            "top_n": 2,
        },
        "construction": {"weighting": "equal_weight"},
    }
    strategy = compile_strategy(dsl)

    with pytest.raises(ValidationError):
        strategy.generate_target_weights(
            "2021-01-02",
            _market_state(
                "2021-01-02",
                [
                    {
                        "date": "2021-01-01",
                        "symbol": "SH600036",
                        "open": 1,
                        "high": 1,
                        "low": 1,
                        "close": 1,
                        "volume": 1,
                    },
                    {
                        "date": "2021-01-02",
                        "symbol": "SH600036",
                        "open": 2,
                        "high": 2,
                        "low": 2,
                        "close": 2,
                        "volume": 1,
                    },
                ],
            ),
            PortfolioState(weights={"SH600036": 0.7, "SH600519": 0.4}),
        )
