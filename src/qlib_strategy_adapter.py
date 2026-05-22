from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
import importlib.util
from pathlib import Path
import sys
import types
from typing import Any

import pandas as pd

from src.dsl import validate_target_weights
from src.models import MarketState, PortfolioState
from src.symbols import normalize_symbol


class QlibIntegrationError(RuntimeError):
    pass


try:
    from qlib.strategy.base import BaseStrategy
except Exception as exc:
    _BASE_STRATEGY_IMPORT_ERROR = exc
    BaseStrategy = object
else:
    _BASE_STRATEGY_IMPORT_ERROR = None


def ensure_qlib_strategy_integration_available() -> None:
    if _BASE_STRATEGY_IMPORT_ERROR is not None:
        raise QlibIntegrationError(
            f"Qlib BaseStrategy is unavailable: {_BASE_STRATEGY_IMPORT_ERROR}"
        )
    _load_order_generator()
    _load_trade_decision()


def _load_order_generator() -> type:
    try:
        from qlib.contrib.strategy.order_generator import OrderGenWOInteract

        return OrderGenWOInteract
    except Exception as import_exc:
        try:
            import qlib

            path = (
                Path(qlib.__file__).resolve().parent
                / "contrib"
                / "strategy"
                / "order_generator.py"
            )
            package_name = "qlib.contrib.strategy"
            if package_name not in sys.modules:
                package = types.ModuleType(package_name)
                package.__path__ = [str(path.parent)]
                sys.modules[package_name] = package
            spec = importlib.util.spec_from_file_location(
                f"{package_name}.order_generator", path
            )
            if spec is None or spec.loader is None:
                raise ImportError(f"cannot load spec for {path}")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module.OrderGenWOInteract
        except Exception as fallback_exc:
            raise QlibIntegrationError(
                "Qlib order generator is unavailable: "
                f"{import_exc}; fallback load failed: {fallback_exc}"
            ) from fallback_exc


def _load_trade_decision() -> type:
    try:
        from qlib.backtest.decision import TradeDecisionWO

        return TradeDecisionWO
    except Exception as exc:
        raise QlibIntegrationError(f"Qlib TradeDecisionWO is unavailable: {exc}") from exc


def _qlib_position_to_portfolio_state(position: Any | None) -> PortfolioState:
    if position is None:
        return PortfolioState()

    state_kwargs: dict[str, Any] = {}

    get_cash = getattr(position, "get_cash", None)
    if callable(get_cash):
        state_kwargs["cash"] = float(get_cash())

    get_amounts = getattr(position, "get_stock_amount_dict", None)
    positions = _normalized_position_mapping(get_amounts()) if callable(get_amounts) else {}
    if positions:
        state_kwargs["positions"] = positions

    get_weights = getattr(position, "get_stock_weight_dict", None)
    if callable(get_weights):
        try:
            weights = _normalized_position_mapping(get_weights())
        except Exception:
            weights = {}
        if weights:
            state_kwargs["weights"] = weights

    entry_price = _entry_prices_from_qlib_position(position, positions)
    if entry_price:
        state_kwargs["entry_price"] = entry_price

    return PortfolioState(**state_kwargs)


def _normalized_position_mapping(values: Any) -> dict[str, float]:
    if values is None:
        return {}
    return {
        normalize_symbol(symbol): float(value)
        for symbol, value in dict(values).items()
        if float(value) != 0.0
    }


def _entry_prices_from_qlib_position(
    position: Any, positions: dict[str, float]
) -> dict[str, float]:
    get_price = getattr(position, "get_stock_price", None)
    if not callable(get_price):
        return {}

    entry_price = {}
    for symbol in positions:
        try:
            price = get_price(symbol)
        except Exception:
            try:
                price = get_price(f"{symbol[2:]}.{symbol[:2]}")
            except Exception:
                continue
        if price is not None:
            entry_price[symbol] = float(price)
    return entry_price


_MISSING_INFRA_ERRORS = (AttributeError, KeyError, TypeError)


class QlibTargetWeightStrategy(BaseStrategy):
    def __init__(
        self,
        compiled_strategy: Any,
        data_provider: Any,
        universe_symbols: list[str] | None = None,
        start: str | None = None,
        end: str | None = None,
        window_days: int = 252,
        order_generator_cls_or_obj: Any | None = None,
        risk_degree: float = 0.95,
        **kwargs: Any,
    ) -> None:
        if _BASE_STRATEGY_IMPORT_ERROR is not None:
            raise QlibIntegrationError(
                f"Qlib BaseStrategy is unavailable: {_BASE_STRATEGY_IMPORT_ERROR}"
            )
        super().__init__(
            outer_trade_decision=kwargs.get("outer_trade_decision"),
            level_infra=kwargs.get("level_infra"),
            common_infra=kwargs.get("common_infra"),
            trade_exchange=kwargs.get("trade_exchange"),
        )
        self.compiled_strategy = compiled_strategy
        self.data_provider = data_provider
        self.universe_symbols = [
            normalize_symbol(symbol)
            for symbol in (universe_symbols or self._symbols_from_strategy())
        ]
        self.start = start
        self.end = end
        self.window_days = window_days
        self.risk_degree = risk_degree
        self.order_generator = self._init_order_generator(order_generator_cls_or_obj)

    def generate_target_weight_position(
        self,
        date: Any = None,
        portfolio_state: PortfolioState | None = None,
        **kwargs: Any,
    ) -> dict[str, float]:
        date_text = self._date_text(
            date or kwargs.get("trade_start_time") or kwargs.get("trade_end_time")
        )
        market_state = self._build_market_state(date_text)
        if portfolio_state is None:
            current = (
                kwargs["current"]
                if "current" in kwargs
                else self._current_trade_position_or_none()
            )
            portfolio_state = _qlib_position_to_portfolio_state(
                current
            )
        weights = self.compiled_strategy.generate_target_weights(
            date=date_text,
            market_state=market_state,
            portfolio_state=portfolio_state,
        )
        return validate_target_weights(weights)

    def generate_trade_decision(self, execute_result: list | None = None) -> Any:
        if self.order_generator is None:
            _load_order_generator()
        trade_step = self.trade_calendar.get_trade_step()
        trade_start_time, trade_end_time = self.trade_calendar.get_step_time(trade_step)
        pred_start_time, pred_end_time = self.trade_calendar.get_step_time(
            trade_step, shift=1
        )
        current = deepcopy(self.trade_position)
        target_weights = self.generate_target_weight_position(
            current=current,
            trade_start_time=trade_start_time,
            trade_end_time=trade_end_time,
        )
        order_list = self.order_generator.generate_order_list_from_target_weight_position(
            current=current,
            trade_exchange=self.trade_exchange,
            risk_degree=self.risk_degree,
            target_weight_position=target_weights,
            pred_start_time=pred_start_time,
            pred_end_time=pred_end_time,
            trade_start_time=trade_start_time,
            trade_end_time=trade_end_time,
        )
        return _load_trade_decision()(order_list, self)

    def _init_order_generator(self, order_generator_cls_or_obj: Any | None) -> Any | None:
        if order_generator_cls_or_obj is not None:
            if isinstance(order_generator_cls_or_obj, type):
                return order_generator_cls_or_obj()
            return order_generator_cls_or_obj
        try:
            return _load_order_generator()()
        except QlibIntegrationError:
            return None

    def _build_market_state(self, date: str) -> MarketState:
        build_market_state = getattr(self.data_provider, "build_market_state", None)
        if callable(build_market_state):
            return build_market_state(date)

        bars = self.data_provider.get_bars(
            self.universe_symbols,
            self._window_start(date),
            date,
        )
        bars = pd.DataFrame(bars).copy()
        if not bars.empty:
            bars["date"] = pd.to_datetime(bars["date"])
            bars["symbol"] = bars["symbol"].map(normalize_symbol)
        return MarketState(date=date, bars=bars)

    def _window_start(self, date: str) -> str:
        if self.start:
            return (pd.Timestamp(self.start) - timedelta(days=self.window_days)).strftime(
                "%Y-%m-%d"
            )
        return (pd.Timestamp(date) - timedelta(days=self.window_days)).strftime("%Y-%m-%d")

    def _symbols_from_strategy(self) -> list[str]:
        universe = getattr(self.compiled_strategy, "dsl", {}).get("universe", {})
        return list(universe.get("symbols", []))

    def _current_trade_position_or_none(self) -> Any | None:
        try:
            return self.trade_position
        except _MISSING_INFRA_ERRORS:
            return None

    @staticmethod
    def _date_text(date: Any) -> str:
        if date is None:
            raise ValueError("date or trade_start_time is required")
        return pd.Timestamp(date).strftime("%Y-%m-%d")
