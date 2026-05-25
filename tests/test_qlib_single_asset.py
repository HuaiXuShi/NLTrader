import pandas as pd
import pytest

qlib_strategy_base = pytest.importorskip(
    "qlib.strategy.base",
    reason="Qlib strategy integration tests require qlib to be installed",
)
BaseStrategy = qlib_strategy_base.BaseStrategy

from src.dsl import ValidationError
from src.models import UniverseSpec
from src.qlib_evaluator import QlibEvaluator, QlibIntegrationError
from src.qlib_strategy_adapter import QlibTargetWeightStrategy
from src.report import map_qlib_result


class FakeProvider:
    provider_uri = "/fake/qlib"
    region = "cn"
    benchmark = "SH000300"

    def __init__(self):
        self.bar_calls = []

    def get_bars(self, symbols, start, end, fields=None):
        self.bar_calls.append(
            {"symbols": symbols, "start": start, "end": end, "fields": fields}
        )
        return pd.DataFrame(
            [
                {
                    "date": "2021-01-04",
                    "symbol": "600036.SH",
                    "open": 10,
                    "high": 10,
                    "low": 10,
                    "close": 10,
                    "volume": 1000,
                }
            ]
        )

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
            "strategy_kind": "timeseries",
            "universe": {"type": "single_symbol", "symbols": ["600036.SH"]},
        }
        self.weights = weights
        self.calls = []

    def generate_target_weights(self, date, market_state, portfolio_state):
        self.calls.append(
            {
                "date": date,
                "market_state": market_state,
                "portfolio_state": portfolio_state,
            }
        )
        return self.weights


class HoldingAwareStrategy:
    def __init__(self):
        self.dsl = {
            "strategy_kind": "timeseries",
            "universe": {"type": "single_symbol", "symbols": ["600036.SH"]},
        }
        self.calls = []

    def generate_target_weights(self, date, market_state, portfolio_state):
        self.calls.append(portfolio_state)
        if portfolio_state.weights.get("SH600036", 0.0) > 0:
            return {}
        return {"SH600036": 1.0}


class FakeQlibPosition:
    def get_cash(self):
        return 12345.0

    def get_stock_amount_dict(self):
        return {"600036.SH": 200.0}

    def get_stock_weight_dict(self):
        return {"600036.SH": 0.4}

    def get_stock_price(self, symbol):
        if symbol == "600036.SH":
            return 11.5
        raise KeyError(symbol)


def test_single_asset_adapter_calls_compiled_strategy_and_returns_validated_weights():
    provider = FakeProvider()
    compiled = RecordingStrategy({"600036.SH": 1.0})
    adapter = QlibTargetWeightStrategy(
        compiled_strategy=compiled,
        data_provider=provider,
        universe_symbols=["600036.SH"],
        start="2021-01-01",
        end="2021-01-05",
    )

    weights = adapter.generate_target_weight_position("2021-01-04")

    assert weights == {"SH600036": 1.0}
    assert provider.bar_calls == [
        {
            "symbols": ["SH600036"],
            "start": "2020-04-24",
            "end": "2021-01-04",
            "fields": None,
        }
    ]
    call = compiled.calls[0]
    assert call["date"] == "2021-01-04"
    assert call["market_state"].date == "2021-01-04"
    assert call["market_state"].bars["symbol"].tolist() == ["SH600036"]
    assert call["portfolio_state"].weights == {}


def test_single_asset_adapter_maps_current_qlib_position_to_portfolio_state():
    provider = FakeProvider()
    compiled = RecordingStrategy({"600036.SH": 0.4})
    adapter = QlibTargetWeightStrategy(
        compiled_strategy=compiled,
        data_provider=provider,
        universe_symbols=["600036.SH"],
        start="2021-01-01",
    )

    adapter.generate_target_weight_position(
        trade_start_time=pd.Timestamp("2021-01-04"),
        current=FakeQlibPosition(),
    )

    portfolio_state = compiled.calls[0]["portfolio_state"]
    assert portfolio_state.cash == 12345.0
    assert portfolio_state.positions == {"SH600036": 200.0}
    assert portfolio_state.weights == {"SH600036": 0.4}
    assert portfolio_state.entry_price == {"SH600036": 11.5}


def test_single_asset_adapter_fetches_warmup_before_backtest_start():
    provider = FakeProvider()
    compiled = RecordingStrategy({"600036.SH": 1.0})
    adapter = QlibTargetWeightStrategy(
        compiled_strategy=compiled,
        data_provider=provider,
        universe_symbols=["600036.SH"],
        start="2021-01-10",
        window_days=5,
    )

    adapter.generate_target_weight_position("2021-01-10")

    assert provider.bar_calls[0]["start"] == "2021-01-05"
    assert provider.bar_calls[0]["end"] == "2021-01-10"


def test_single_asset_adapter_accepts_qlib_target_weight_signature():
    provider = FakeProvider()
    compiled = RecordingStrategy({"600036.SH": 1.0})
    adapter = QlibTargetWeightStrategy(
        compiled_strategy=compiled,
        data_provider=provider,
        universe_symbols=["600036.SH"],
        start="2021-01-01",
    )

    weights = adapter.generate_target_weight_position(
        score=None,
        current=None,
        trade_start_time=pd.Timestamp("2021-01-04"),
        trade_end_time=pd.Timestamp("2021-01-04"),
    )

    assert weights == {"SH600036": 1.0}
    assert compiled.calls[0]["date"] == "2021-01-04"


def test_single_asset_adapter_is_real_qlib_base_strategy_subclass():
    assert issubclass(QlibTargetWeightStrategy, BaseStrategy)


def test_single_asset_adapter_generate_trade_decision_uses_order_generator():
    provider = FakeProvider()
    compiled = RecordingStrategy({"600036.SH": 1.0})
    calendar = FakeTradeCalendar()
    trade_account = FakeTradeAccount()
    trade_exchange = object()
    adapter = QlibTargetWeightStrategy(
        compiled_strategy=compiled,
        data_provider=provider,
        universe_symbols=["600036.SH"],
        start="2021-01-01",
        level_infra={"trade_calendar": calendar},
        common_infra={
            "trade_account": trade_account,
            "trade_exchange": trade_exchange,
        },
    )
    adapter.order_generator = RecordingOrderGenerator([])

    decision = adapter.generate_trade_decision()

    assert adapter.order_generator.calls[0]["target_weight_position"] == {
        "SH600036": 1.0
    }
    assert adapter.order_generator.calls[0]["current"] is not trade_account.position
    assert decision.get_decision() == []
    assert compiled.calls[0]["date"] == "2021-01-04"


def test_single_asset_adapter_generate_trade_decision_propagates_current_holdings():
    provider = FakeProvider()
    compiled = HoldingAwareStrategy()
    calendar = FakeTradeCalendar()
    trade_account = FakeTradeAccount(FakeQlibPosition())
    trade_exchange = object()
    adapter = QlibTargetWeightStrategy(
        compiled_strategy=compiled,
        data_provider=provider,
        universe_symbols=["600036.SH"],
        start="2021-01-01",
        level_infra={"trade_calendar": calendar},
        common_infra={
            "trade_account": trade_account,
            "trade_exchange": trade_exchange,
        },
    )
    adapter.order_generator = RecordingOrderGenerator([])

    adapter.generate_trade_decision()

    assert adapter.order_generator.calls[0]["target_weight_position"] == {}
    assert compiled.calls[0].weights == {"SH600036": 0.4}


def test_single_asset_adapter_rejects_negative_weights():
    provider = FakeProvider()
    compiled = RecordingStrategy({"SH600036": -0.1})
    adapter = QlibTargetWeightStrategy(
        compiled_strategy=compiled,
        data_provider=provider,
        universe_symbols=["SH600036"],
        start="2021-01-01",
    )

    with pytest.raises(ValidationError):
        adapter.generate_target_weight_position("2021-01-04")


def test_evaluator_builds_default_qlib_config_and_maps_report():
    provider = FakeProvider()
    compiled = RecordingStrategy({"SH600036": 1.0})
    calls = []

    def fake_runner(strategy, backtest_config):
        calls.append({"strategy": strategy, "backtest_config": backtest_config})
        report = pd.DataFrame(
            {"return": [0.01, -0.02], "bench": [0.005, -0.01], "turnover": [0.2, 0.1]},
            index=pd.to_datetime(["2021-01-04", "2021-01-05"]),
        )
        positions = pd.DataFrame(
            {"symbol": ["SH600036"], "weight": [1.0]},
            index=pd.to_datetime(["2021-01-04"]),
        )
        analysis = {
            "annualized_return": 0.12,
            "max_drawdown": -0.08,
            "information_ratio": 1.2,
        }
        return report, positions, analysis

    evaluator = QlibEvaluator(data_provider=provider, runner=fake_runner)

    result = evaluator.run(
        compiled,
        UniverseSpec(type="single_symbol", symbols=["600036.SH"]),
        "2021-01-01",
        "2021-01-05",
    )

    config = calls[0]["backtest_config"]
    assert config["account"] == 100000000.0
    assert config["benchmark"] == "SH000300"
    assert config["exchange_kwargs"] == {
        "freq": "day",
        "limit_threshold": 0.095,
        "deal_price": "close",
        "open_cost": 0.0005,
        "close_cost": 0.0015,
        "min_cost": 5.0,
    }
    assert calls[0]["strategy"].compiled_strategy is compiled
    assert result.qlib_report is not None
    assert result.qlib_positions is not None
    assert result.qlib_analysis == {
        "annualized_return": 0.12,
        "max_drawdown": -0.08,
        "information_ratio": 1.2,
    }
    assert result.metrics["annualized_return"] == 0.12
    assert result.metrics["max_drawdown"] == -0.08
    assert result.metrics["information_ratio"] == 1.2
    assert result.metrics["total_return"] == pytest.approx(-0.0102)
    assert result.metrics["turnover"] == pytest.approx(0.3)
    assert result.capability_summary["provider_uri"] == "/fake/qlib"
    assert result.capability_summary["account"] == 100000000.0
    assert result.capability_summary["freq"] == "day"
    assert result.capability_summary["deal_price"] == "close"
    assert result.capability_summary["execution_note"] == (
        "Qlib daily executor with target-weight adapter; "
        "signals are generated for the current Qlib trade step; "
        "OrderGenWOInteract sizes with prior close when needed; "
        "no custom matching engine"
    )


def test_default_evaluator_fails_clearly_when_strategy_integration_unavailable(monkeypatch):
    provider = FakeProvider()
    compiled = RecordingStrategy({"SH600036": 1.0})
    evaluator = QlibEvaluator(data_provider=provider)
    monkeypatch.setattr(
        "src.qlib_evaluator.ensure_qlib_strategy_integration_available",
        lambda: (_ for _ in ()).throw(QlibIntegrationError("broken qlib strategy")),
    )

    with pytest.raises(QlibIntegrationError, match="broken qlib strategy"):
        evaluator.run(
            compiled,
            UniverseSpec(type="single_symbol", symbols=["600036.SH"]),
            "2021-01-01",
            "2021-01-05",
        )


def test_evaluator_adds_warning_when_risk_analysis_fails():
    provider = FakeProvider()
    evaluator = QlibEvaluator(data_provider=provider, runner=lambda *_: None)
    report = pd.DataFrame(
        {"return": [0.01]}, index=pd.to_datetime(["2021-01-04"])
    )

    analysis, warnings = evaluator._risk_analysis(
        report, lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom"))
    )

    assert analysis == {}
    assert warnings == ["Qlib risk_analysis failed: boom"]


def test_report_mapping_preserves_qlib_outputs_and_computes_equity_curve():
    report = pd.DataFrame(
        {"return": [0.10, -0.05], "cost": [0.001, 0.002]},
        index=pd.to_datetime(["2021-01-04", "2021-01-05"]),
    )
    positions = pd.DataFrame({"symbol": ["SH600036"], "weight": [1.0]})
    analysis = {"annualized_return": 0.2, "sharpe": 1.5, "max_drawdown": -0.1}
    capability = {
        "provider_uri": "/fake/qlib",
        "region": "cn",
        "benchmark": "SH000300",
        "deal_price": "close",
        "limit_threshold": 0.095,
        "open_cost": 0.0005,
        "close_cost": 0.0015,
        "min_cost": 5.0,
        "execution_note": "Qlib daily executor with target-weight adapter",
    }

    result = map_qlib_result(report, positions, analysis, capability)

    assert result.qlib_report is report
    assert result.qlib_positions is positions
    assert result.qlib_analysis == analysis
    assert result.equity_curve["equity"].tolist() == pytest.approx([1.1, 1.045])
    assert result.metrics["total_return"] == pytest.approx(0.045)
    assert result.metrics["annualized_return"] == 0.2
    assert result.metrics["sharpe"] == 1.5
    assert result.metrics["max_drawdown"] == -0.1
    assert result.metrics["num_trades"] == 0


def test_report_mapping_preserves_positions_dict_and_does_not_crash_num_trades():
    report = pd.DataFrame(
        {"return": [0.01]}, index=pd.to_datetime(["2021-01-04"])
    )
    positions = {pd.Timestamp("2021-01-04"): object()}

    result = map_qlib_result(
        report,
        positions,
        {"annualized_return": 0.1},
        {
            "provider_uri": "/fake/qlib",
            "region": "cn",
            "benchmark": "SH000300",
            "deal_price": "close",
            "limit_threshold": 0.095,
            "open_cost": 0.0005,
            "close_cost": 0.0015,
            "min_cost": 5.0,
            "execution_note": "Qlib daily executor with target-weight adapter; same-day close execution; no signal lag",
        },
    )

    assert result.qlib_positions is positions
    assert result.positions_history is positions
    assert result.metrics["num_trades"] == 0


class FakeTradeCalendar:
    def get_trade_step(self):
        return 0

    def get_step_time(self, trade_step=None, shift=0):
        if shift == 1:
            return pd.Timestamp("2021-01-03"), pd.Timestamp("2021-01-03")
        return pd.Timestamp("2021-01-04"), pd.Timestamp("2021-01-04")


class FakeTradeAccount:
    def __init__(self, position=None):
        self.position = object() if position is None else position

    @property
    def current_position(self):
        return self.position


class RecordingOrderGenerator:
    def __init__(self, orders):
        self.orders = orders
        self.calls = []

    def generate_order_list_from_target_weight_position(self, **kwargs):
        self.calls.append(kwargs)
        return self.orders
