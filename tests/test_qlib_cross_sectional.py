import pandas as pd
import pytest

from src.dsl import ValidationError
from src.models import UniverseSpec
from src.qlib_evaluator import QlibEvaluator
from src.qlib_strategy_adapter import QlibTargetWeightStrategy


class FakeProvider:
    provider_uri = "/fake/qlib"
    region = "cn"
    benchmark = "SH000300"

    def __init__(self):
        self.resolve_calls = []

    def get_bars(self, symbols, start, end, fields=None):
        return pd.DataFrame(
            [
                {
                    "date": "2021-02-26",
                    "symbol": symbol,
                    "open": index + 1.0,
                    "high": index + 1.0,
                    "low": index + 1.0,
                    "close": index + 1.0,
                    "volume": 1000,
                }
                for index, symbol in enumerate(symbols)
            ]
        )

    def resolve_universe(self, universe_spec, start, end):
        self.resolve_calls.append(
            {"universe_spec": universe_spec, "start": start, "end": end}
        )
        return ["600036.SH", "000001.SZ"]

    def get_capabilities(self):
        return {
            "provider_name": "FakeProvider",
            "provider_uri": self.provider_uri,
            "region": self.region,
            "benchmark": self.benchmark,
        }


class RecordingStrategy:
    def __init__(self, weights):
        self.dsl = {
            "strategy_kind": "cross_sectional",
            "universe": {
                "type": "symbol_list",
                "symbols": ["600036.SH", "000001.SZ"],
            },
        }
        self.weights = weights
        self.calls = []

    def generate_target_weights(self, date, market_state, portfolio_state):
        self.calls.append((date, market_state, portfolio_state))
        return self.weights


def test_cross_sectional_adapter_uses_same_target_weight_path():
    provider = FakeProvider()
    compiled = RecordingStrategy({"600036.SH": 0.5, "000001.SZ": 0.5})
    adapter = QlibTargetWeightStrategy(
        compiled_strategy=compiled,
        data_provider=provider,
        universe_symbols=["600036.SH", "000001.SZ"],
        start="2021-02-01",
        end="2021-02-26",
    )

    weights = adapter.generate_target_weight_position("2021-02-26")

    assert weights == {"SH600036": 0.5, "SZ000001": 0.5}
    _, market_state, _ = compiled.calls[0]
    assert sorted(market_state.bars["symbol"].unique().tolist()) == [
        "SH600036",
        "SZ000001",
    ]


def test_cross_sectional_adapter_rejects_overallocated_weights():
    provider = FakeProvider()
    compiled = RecordingStrategy({"SH600036": 0.7, "SZ000001": 0.4})
    adapter = QlibTargetWeightStrategy(
        compiled_strategy=compiled,
        data_provider=provider,
        universe_symbols=["SH600036", "SZ000001"],
        start="2021-02-01",
    )

    with pytest.raises(ValidationError):
        adapter.generate_target_weight_position("2021-02-26")


def test_evaluator_resolves_cross_sectional_universe_for_adapter_and_config():
    provider = FakeProvider()
    compiled = RecordingStrategy({"SH600036": 0.5, "SZ000001": 0.5})
    calls = []

    def fake_runner(strategy, backtest_config):
        calls.append({"strategy": strategy, "backtest_config": backtest_config})
        report = pd.DataFrame(
            {"return": [0.01], "turnover": [0.4]},
            index=pd.to_datetime(["2021-02-26"]),
        )
        return report, pd.DataFrame(), {"annualized_return": 0.1}

    evaluator = QlibEvaluator(data_provider=provider, runner=fake_runner)
    universe = UniverseSpec(
        type="symbol_list", symbols=["600036.SH", "000001.SZ"]
    )

    result = evaluator.run(compiled, universe, "2021-02-01", "2021-02-26")

    assert provider.resolve_calls == [
        {"universe_spec": universe, "start": "2021-02-01", "end": "2021-02-26"}
    ]
    assert calls[0]["strategy"].universe_symbols == ["SH600036", "SZ000001"]
    assert calls[0]["backtest_config"]["benchmark"] == "SH000300"
    assert result.metrics["turnover"] == pytest.approx(0.4)
    assert result.capability_summary["limit_threshold"] == 0.095
