import pandas as pd
import pytest

from src.compiler import compile_strategy
from src.config import Settings
from src.models import BacktestResult, MarketState, ParseResult, PortfolioState
from src.parser import LLMOutputContractError, StrategyParser
from src.pipeline import run_backtest_pipeline
from src.qlib_strategy_adapter import QlibTargetWeightStrategy


class FakeEvaluator:
    def __init__(self, result=None):
        self.result = result or _backtest_result()
        self.calls = []

    def run(self, compiled_strategy, universe_spec, start, end):
        self.calls.append(
            {
                "compiled_strategy": compiled_strategy,
                "universe_spec": universe_spec,
                "start": start,
                "end": end,
            }
        )
        return self.result


class StaticParser:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def parse(self, text, *, fallback=True):
        self.calls.append({"text": text, "fallback": fallback})
        return self.result


class RaisingParser:
    def __init__(self, exc):
        self.exc = exc
        self.calls = []

    def parse(self, text, *, fallback=True):
        self.calls.append({"text": text, "fallback": fallback})
        raise self.exc


def test_case_1_static_parser_single_stock_ma_compiles_with_injected_evaluator():
    evaluator = FakeEvaluator()
    parser = StaticParser(_valid_timeseries_parse_result())

    result = run_backtest_pipeline(
        "针对招商银行600036，5日均线上穿20日均线买入，跌破10日均线卖出。",
        "2021-01-01",
        "2021-03-31",
        parser=parser,
        evaluator=evaluator,
        fallback=False,
    )

    assert result.status == "ok"
    assert result.parse_result.strategy_kind == "timeseries"
    assert result.backtest_result is evaluator.result
    assert result.backtest_result.metrics["num_trades"] == 0
    assert result.compiled_strategy is not None
    assert hasattr(result.compiled_strategy, "generate_target_weights")
    assert len(evaluator.calls) == 1
    assert evaluator.calls[0]["universe_spec"].symbols == ["SH600036"]
    assert parser.calls == [
        {
            "text": "针对招商银行600036，5日均线上穿20日均线买入，跌破10日均线卖出。",
            "fallback": False,
        }
    ]


def test_case_2_static_parser_stop_loss_uses_injected_evaluator():
    evaluator = FakeEvaluator()
    parser = StaticParser(_valid_timeseries_stop_loss_parse_result())

    result = run_backtest_pipeline(
        "针对招商银行600036，5日均线上穿20日均线买入，亏损8%卖出。",
        "2021-01-01",
        "2021-03-31",
        parser=parser,
        evaluator=evaluator,
        fallback=False,
    )

    assert result.status == "ok"
    assert result.parse_result.dsl["risk"]["stop_loss"] == pytest.approx(0.08)
    assert result.backtest_result is evaluator.result
    assert len(evaluator.calls) == 1

    weights = result.compiled_strategy.generate_target_weights(
        "2021-01-02",
        MarketState(
            date="2021-01-02",
            bars=[
                {
                    "date": "2021-01-01",
                    "symbol": "SH600036",
                    "open": 10.0,
                    "high": 10.0,
                    "low": 10.0,
                    "close": 10.0,
                    "volume": 1000,
                },
                {
                    "date": "2021-01-02",
                    "symbol": "SH600036",
                    "open": 9.1,
                    "high": 9.1,
                    "low": 9.1,
                    "close": 9.1,
                    "volume": 1000,
                },
            ],
        ),
        PortfolioState(weights={"SH600036": 1.0}, entry_price={"SH600036": 10.0}),
    )
    assert weights == {}


def test_case_3_static_parser_fuzzy_volume_reports_uncertainty_with_injected_evaluator():
    result = run_backtest_pipeline(
        "针对招商银行600036，放量上涨时买入，趋势破了就卖。",
        "2021-01-01",
        "2021-03-31",
        parser=StaticParser(_fuzzy_volume_parse_result()),
        evaluator=FakeEvaluator(),
        fallback=False,
    )

    assert result.parse_result.assumptions or result.parse_result.warnings or result.warnings


def test_case_4_static_parser_monthly_momentum_top_n_symbol_pool_uses_injected_evaluator():
    evaluator = FakeEvaluator()
    parser = StaticParser(_valid_cross_sectional_top_n_parse_result())

    result = run_backtest_pipeline(
        "每月调仓，在股票池600036、000001、600519、000858、300750、002415、601318、601888、"
        "600030、601166、000333、600900中选择过去20日涨幅最高的10只股票等权持有。",
        "2021-01-01",
        "2021-06-30",
        parser=parser,
        evaluator=evaluator,
        fallback=False,
    )

    dsl = result.parse_result.dsl
    assert result.status == "ok"
    assert dsl["strategy_kind"] == "cross_sectional"
    assert dsl["rebalance"]["freq"] == "monthly"
    assert dsl["selection"]["score"]["factor"] == "RETURN_N"
    assert dsl["selection"]["score"]["params"] == [20]
    assert dsl["selection"]["top_n"] == 10
    assert dsl["construction"]["weighting"] == "equal_weight"
    assert len(evaluator.calls) == 1
    assert parser.calls == [
        {
            "text": "每月调仓，在股票池600036、000001、600519、000858、300750、002415、601318、601888、600030、601166、000333、600900中选择过去20日涨幅最高的10只股票等权持有。",
            "fallback": False,
        }
    ]


def test_case_5_static_parser_missing_universe_does_not_run_evaluator():
    evaluator = FakeEvaluator()
    parser = StaticParser(_unsupported_missing_universe_parse_result())

    result = run_backtest_pipeline(
        "每月选过去20日涨幅最高的10只股票等权持有。",
        "2021-01-01",
        "2021-06-30",
        parser=parser,
        evaluator=evaluator,
        fallback=False,
    )

    warnings = " ".join(result.warnings + result.parse_result.warnings)
    explicit_warning = any(
        keyword in warnings.lower()
        for keyword in ("universe", "股票池", "pool", "范围", "未明确", "缺少")
    )

    assert result.status in {"unsupported", "validation_error"}
    assert explicit_warning
    assert evaluator.calls == []


def test_case_6_unsupported_minute_strategy_does_not_run_evaluator():
    evaluator = FakeEvaluator()

    result = run_backtest_pipeline(
        "招商银行600036，5分钟均线上穿20分钟均线买入。",
        "2021-01-01",
        "2021-03-31",
        evaluator=evaluator,
        fallback=False,
    )

    assert result.status == "unsupported"
    assert result.compiled_strategy is None
    assert result.backtest_result is None
    assert evaluator.calls == []


def test_case_7_missing_qlib_provider_path_returns_readable_data_error(monkeypatch):
    monkeypatch.setenv("QLIB_PROVIDER_URI", "/tmp/nltrader-missing-qlib-provider")
    parser = StaticParser(_valid_timeseries_parse_result())

    result = run_backtest_pipeline(
        "招商银行600036，5日均线上穿20日均线买入。",
        "2021-01-01",
        "2021-03-31",
        parser=parser,
    )

    assert result.status == "data_error"
    assert result.backtest_result is None
    assert any("Qlib provider_uri" in warning or "Qlib is not installed" in warning for warning in result.warnings)
    assert not any("Traceback" in warning for warning in result.warnings)


def test_case_8_capability_summary_is_preserved_from_evaluator_result():
    expected = _backtest_result(
        capability_summary={
            "provider_uri": "/fake/qlib",
            "region": "cn",
            "benchmark": "SH000300",
            "account": 100000000.0,
            "freq": "day",
            "deal_price": "close",
            "limit_threshold": 0.095,
            "open_cost": 0.0005,
            "close_cost": 0.0015,
            "min_cost": 5.0,
        }
    )

    result = run_backtest_pipeline(
        "招商银行600036，5日均线上穿20日均线买入。",
        "2021-01-01",
        "2021-03-31",
        parser=StaticParser(_valid_timeseries_parse_result()),
        evaluator=FakeEvaluator(expected),
    )

    summary = result.backtest_result.capability_summary
    for key in (
        "provider_uri",
        "region",
        "benchmark",
        "account",
        "freq",
        "deal_price",
        "limit_threshold",
        "open_cost",
        "close_cost",
        "min_cost",
    ):
        assert key in summary


def test_case_9_api_failure_fallback_has_explicit_warning():
    parser = StrategyParser(Settings(llm_api_base=None, llm_api_key=None, llm_model=None))

    result = run_backtest_pipeline(
        "招商银行600036，5日均线上穿20日均线买入，跌破10日均线卖出。",
        "2021-01-01",
        "2021-03-31",
        parser=parser,
        evaluator=FakeEvaluator(),
        fallback=True,
    )

    assert result.status == "ok"
    assert any("fallback" in warning.lower() for warning in result.warnings)


def test_case_9b_parser_contract_error_returns_validation_error_without_running_evaluator():
    evaluator = FakeEvaluator()
    parser = RaisingParser(LLMOutputContractError("LLM output failed parser contract after repair"))

    result = run_backtest_pipeline(
        "招商银行600036，5日均线上穿20日均线买入。",
        "2021-01-01",
        "2021-03-31",
        parser=parser,
        evaluator=evaluator,
        fallback=True,
    )

    assert result.status == "validation_error"
    assert result.parse_result.strategy_kind == "unsupported"
    assert result.parse_result.dsl == {}
    assert evaluator.calls == []
    assert any("after repair" in warning for warning in result.warnings)


def test_case_10_timeseries_and_cross_sectional_share_qlib_target_weight_adapter():
    provider = AdapterFakeProvider()
    timeseries_strategy = compile_strategy(_valid_timeseries_parse_result().dsl)
    cross_sectional_strategy = compile_strategy(_valid_cross_sectional_parse_result().dsl)

    timeseries_adapter = QlibTargetWeightStrategy(
        compiled_strategy=timeseries_strategy,
        data_provider=provider,
        universe_symbols=["SH600036"],
        start="2021-01-01",
        end="2021-01-04",
    )
    cross_sectional_adapter = QlibTargetWeightStrategy(
        compiled_strategy=cross_sectional_strategy,
        data_provider=provider,
        universe_symbols=["SH600036", "SZ000001"],
        start="2021-01-01",
        end="2021-01-04",
    )

    timeseries_weights = timeseries_adapter.generate_target_weight_position(
        "2021-01-04"
    )
    cross_sectional_weights = cross_sectional_adapter.generate_target_weight_position(
        "2021-01-04"
    )

    assert type(timeseries_adapter) is QlibTargetWeightStrategy
    assert type(cross_sectional_adapter) is QlibTargetWeightStrategy
    assert isinstance(timeseries_weights, dict)
    assert isinstance(cross_sectional_weights, dict)
    assert set(timeseries_weights).issubset({"SH600036"})
    assert set(cross_sectional_weights).issubset({"SH600036", "SZ000001"})
    assert sum(timeseries_weights.values()) <= 1.0
    assert sum(cross_sectional_weights.values()) <= 1.0
    assert provider.calls == [
        {"symbols": ["SH600036"], "start": "2020-04-24", "end": "2021-01-04"},
        {
            "symbols": ["SH600036", "SZ000001"],
            "start": "2020-04-24",
            "end": "2021-01-04",
        },
    ]


class AdapterFakeProvider:
    def __init__(self):
        self.calls = []

    def get_bars(self, symbols, start, end, fields=None):
        self.calls.append({"symbols": symbols, "start": start, "end": end})
        dates = pd.date_range("2021-01-01", "2021-01-04", freq="D")
        rows = []
        for symbol_index, symbol in enumerate(symbols):
            for day_index, date in enumerate(dates):
                close = 10.0 + symbol_index + day_index
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
        return pd.DataFrame(rows)


def _backtest_result(capability_summary=None):
    return BacktestResult(
        capability_summary=capability_summary or {"provider_uri": "/fake/qlib"},
        qlib_report=pd.DataFrame(
            {"return": [0.0], "turnover": [0.0]},
            index=pd.to_datetime(["2021-01-04"]),
        ),
        qlib_positions=pd.DataFrame(),
        qlib_analysis={},
        metrics={"num_trades": 0},
    )


def _valid_timeseries_parse_result():
    return ParseResult(
        dsl={
            "strategy_kind": "timeseries",
            "market": "CN_A",
            "frequency": "D",
            "universe": {"type": "single_symbol", "symbols": ["SH600036"]},
            "rebalance": {"freq": "daily"},
            "signal": {
                "entry_rules": [
                    {
                        "lhs": {"indicator": "SMA", "params": [5]},
                        "op": "cross_above",
                        "rhs": {"indicator": "SMA", "params": [20]},
                    }
                ],
                "exit_rules": [],
            },
        },
        strategy_kind="timeseries",
    )


def _valid_timeseries_stop_loss_parse_result():
    result = _valid_timeseries_parse_result()
    result.dsl["risk"] = {"stop_loss": 0.08}
    return result


def _fuzzy_volume_parse_result():
    result = _valid_timeseries_parse_result()
    result.assumptions = ["将'放量上涨'近似为价格趋势确认。"]
    result.warnings = ["原始描述存在模糊性，已做保守解释。"]
    return result


def _valid_cross_sectional_parse_result():
    return ParseResult(
        dsl={
            "strategy_kind": "cross_sectional",
            "market": "CN_A",
            "frequency": "D",
            "universe": {"type": "symbol_list", "symbols": ["SH600036", "SZ000001"]},
            "rebalance": {"freq": "monthly"},
            "selection": {
                "filters": [],
                "score": {"factor": "RETURN_N", "params": [20]},
                "rank_order": "desc",
                "top_n": 1,
            },
            "construction": {"weighting": "equal_weight"},
        },
        strategy_kind="cross_sectional",
    )


def _valid_cross_sectional_top_n_parse_result():
    return ParseResult(
        dsl={
            "strategy_kind": "cross_sectional",
            "market": "CN_A",
            "frequency": "D",
            "universe": {
                "type": "symbol_list",
                "symbols": [
                    "SH600036",
                    "SZ000001",
                    "SH600519",
                    "SZ000858",
                    "SZ300750",
                    "SZ002415",
                    "SH601318",
                    "SH601888",
                    "SH600030",
                    "SH601166",
                    "SZ000333",
                    "SH600900",
                ],
            },
            "rebalance": {"freq": "monthly"},
            "selection": {
                "filters": [],
                "score": {"factor": "RETURN_N", "params": [20]},
                "rank_order": "desc",
                "top_n": 10,
            },
            "construction": {"weighting": "equal_weight"},
        },
        strategy_kind="cross_sectional",
    )


def _unsupported_missing_universe_parse_result():
    return ParseResult(
        dsl={},
        strategy_kind="unsupported",
        warnings=["缺少明确股票池或 universe，无法执行横截面选股。"],
    )
