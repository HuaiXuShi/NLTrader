from __future__ import annotations

from typing import Any, Callable

import pandas as pd

from src.config import Settings, load_settings
from src.models import BacktestResult, UniverseSpec
from src.qlib_strategy_adapter import (
    QlibIntegrationError,
    QlibTargetWeightStrategy,
    ensure_qlib_strategy_integration_available,
)
from src.report import map_qlib_result
from src.symbols import normalize_symbol


Runner = Callable[[QlibTargetWeightStrategy, dict[str, Any]], tuple[Any, Any, Any]]


class QlibEvaluator:
    def __init__(
        self,
        data_provider: Any,
        settings: Settings | None = None,
        runner: Runner | None = None,
    ) -> None:
        self.data_provider = data_provider
        self.settings = settings or load_settings()
        self.runner = runner or self._run_qlib_backtest

    def run(
        self,
        compiled_strategy: Any,
        universe_spec: UniverseSpec,
        start: str,
        end: str,
    ) -> BacktestResult:
        if self.runner == self._run_qlib_backtest:
            ensure_qlib_strategy_integration_available()
        universe_symbols = self._resolve_universe(universe_spec, start, end)
        strategy = QlibTargetWeightStrategy(
            compiled_strategy=compiled_strategy,
            data_provider=self.data_provider,
            universe_symbols=universe_symbols,
            start=start,
            end=end,
        )
        backtest_config = self._backtest_config(start, end)
        qlib_report, qlib_positions, qlib_analysis = self.runner(
            strategy, backtest_config
        )
        qlib_analysis, risk_warnings = self._normalize_runner_analysis(qlib_analysis)
        return map_qlib_result(
            qlib_report,
            qlib_positions,
            qlib_analysis,
            self._capability_summary(backtest_config),
            strategy_summary=self._strategy_summary(compiled_strategy, universe_spec),
            warnings=risk_warnings,
        )

    def _backtest_config(self, start: str, end: str) -> dict[str, Any]:
        return {
            "start_time": start,
            "end_time": end,
            "account": self.settings.qlib_account,
            "benchmark": self._benchmark(),
            "exchange_kwargs": {
                "freq": "day",
                "limit_threshold": self.settings.qlib_limit_threshold,
                "deal_price": self.settings.qlib_deal_price,
                "open_cost": self.settings.qlib_open_cost,
                "close_cost": self.settings.qlib_close_cost,
                "min_cost": self.settings.qlib_min_cost,
            },
        }

    def _run_qlib_backtest(
        self, strategy: QlibTargetWeightStrategy, backtest_config: dict[str, Any]
    ) -> tuple[Any, Any, Any]:
        try:
            from qlib.contrib.evaluate import backtest_daily, risk_analysis
        except Exception as exc:
            raise QlibIntegrationError(f"Qlib backtest is unavailable: {exc}") from exc

        report, positions = backtest_daily(strategy=strategy, **backtest_config)
        analysis, warnings = self._risk_analysis(report, risk_analysis)
        if warnings:
            analysis = {"analysis": analysis, "warnings": warnings}
        return report, positions, analysis

    def _risk_analysis(
        self, report: Any, risk_analysis: Callable[..., Any]
    ) -> tuple[dict[str, Any], list[str]]:
        frame = pd.DataFrame(report)
        if "return" not in frame.columns:
            return {}, []
        try:
            return self._flatten_analysis(risk_analysis(frame["return"], freq="day")), []
        except Exception as exc:
            return {}, [f"Qlib risk_analysis failed: {exc}"]

    def _normalize_runner_analysis(self, value: Any) -> tuple[Any, list[str]]:
        if isinstance(value, dict) and set(value) == {"analysis", "warnings"}:
            return value["analysis"], list(value["warnings"])
        return value, []

    def _flatten_analysis(self, analysis: Any) -> dict[str, Any]:
        if isinstance(analysis, pd.Series):
            return analysis.dropna().to_dict()
        if isinstance(analysis, pd.DataFrame):
            if len(analysis.columns) == 1:
                return analysis.iloc[:, 0].dropna().to_dict()
            return analysis.dropna(how="all").to_dict()
        if isinstance(analysis, dict):
            return dict(analysis)
        return {}

    def _resolve_universe(
        self, universe_spec: UniverseSpec, start: str, end: str
    ) -> list[str]:
        resolver = getattr(self.data_provider, "resolve_universe", None)
        if callable(resolver):
            return [normalize_symbol(symbol) for symbol in resolver(universe_spec, start, end)]
        return [normalize_symbol(symbol) for symbol in universe_spec.symbols]

    def _capability_summary(self, backtest_config: dict[str, Any]) -> dict[str, Any]:
        provider_summary = {}
        get_capabilities = getattr(self.data_provider, "get_capabilities", None)
        if callable(get_capabilities):
            provider_summary = dict(get_capabilities())

        exchange = backtest_config["exchange_kwargs"]
        return provider_summary | {
            "provider_uri": provider_summary.get(
                "provider_uri",
                getattr(self.data_provider, "provider_uri", self.settings.qlib_provider_uri),
            ),
            "region": provider_summary.get(
                "region", getattr(self.data_provider, "region", self.settings.qlib_region)
            ),
            "benchmark": backtest_config["benchmark"],
            "account": backtest_config["account"],
            "freq": exchange["freq"],
            "deal_price": exchange["deal_price"],
            "limit_threshold": exchange["limit_threshold"],
            "open_cost": exchange["open_cost"],
            "close_cost": exchange["close_cost"],
            "min_cost": exchange["min_cost"],
            "execution_note": (
                "Qlib daily executor with target-weight adapter; "
                "signals are generated for the current Qlib trade step; "
                "OrderGenWOInteract sizes with prior close when needed; "
                "no custom matching engine"
            ),
        }

    def _benchmark(self) -> str:
        return getattr(self.data_provider, "benchmark", None) or self.settings.qlib_benchmark

    @staticmethod
    def _strategy_summary(compiled_strategy: Any, universe_spec: UniverseSpec) -> dict[str, Any]:
        dsl = getattr(compiled_strategy, "dsl", {})
        return {
            "strategy_kind": dsl.get("strategy_kind"),
            "universe_summary": universe_spec.model_dump(),
        }
