from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from src.dsl import ValidationError, validate_dsl, validate_target_weights
from src.indicators import calculate_indicator
from src.models import MarketState, PortfolioState
from src.symbols import normalize_symbol


def compile_strategy(dsl: dict[str, Any]) -> "CompiledStrategy":
    validated = validate_dsl(dsl)
    return CompiledStrategy(validated)


@dataclass
class CompiledStrategy:
    dsl: dict[str, Any]
    warnings: list[str] = field(default_factory=list)

    def generate_target_weights(
        self,
        date: str,
        market_state: MarketState,
        portfolio_state: PortfolioState,
    ) -> dict[str, float]:
        if self.dsl["strategy_kind"] == "timeseries":
            weights = self._generate_timeseries_weights(
                date, market_state, portfolio_state
            )
        else:
            weights = self._generate_cross_sectional_weights(
                date, market_state, portfolio_state
            )
        return validate_target_weights(weights)

    def _generate_timeseries_weights(
        self,
        date: str,
        market_state: MarketState,
        portfolio_state: PortfolioState,
    ) -> dict[str, float]:
        symbol = self.dsl["universe"]["symbols"][0]
        requested_date = pd.Timestamp(date)
        bars = _prepare_bars(market_state.bars, date)
        symbol_bars = bars[bars["symbol"] == symbol]
        if symbol_bars.empty or symbol_bars["date"].iloc[-1] != requested_date:
            return portfolio_state.weights if _is_holding(portfolio_state, symbol) else {}

        if _stop_loss_triggered(self.dsl.get("risk", {}), symbol_bars, portfolio_state):
            return {}

        signal = self.dsl.get("signal", {})
        holding = _is_holding(portfolio_state, symbol)
        exit_rules = signal.get("exit_rules", [])
        if holding and any(_evaluate_rule(rule, symbol_bars) for rule in exit_rules):
            return {}

        if holding:
            return {symbol: 1.0}

        entry_rules = signal.get("entry_rules", [])
        if entry_rules and all(_evaluate_rule(rule, symbol_bars) for rule in entry_rules):
            return {symbol: 1.0}
        return {}

    def _generate_cross_sectional_weights(
        self,
        date: str,
        market_state: MarketState,
        portfolio_state: PortfolioState,
    ) -> dict[str, float]:
        freq = self.dsl.get("rebalance", {}).get("freq", "daily")
        requested_date = pd.Timestamp(date)
        bars = _prepare_bars(market_state.bars, date)
        if bars.empty or not (bars["date"] == requested_date).any():
            return portfolio_state.weights
        if not _is_rebalance_day(freq, date, bars):
            return portfolio_state.weights

        universe = _resolve_universe(self.dsl["universe"], bars)
        selection = self.dsl["selection"]
        current_symbols = set(bars.loc[bars["date"] == requested_date, "symbol"])
        candidates: list[str] = []
        for symbol in universe:
            if symbol not in current_symbols:
                continue
            symbol_bars = bars[bars["symbol"] == symbol]
            if symbol_bars.empty:
                continue
            filters = selection.get("filters", [])
            if all(_evaluate_rule(rule, symbol_bars) for rule in filters):
                candidates.append(symbol)

        scores = _score_symbols(candidates, bars, selection["score"])
        if "top_n" in selection:
            requested = selection["top_n"]
            ordered = sorted(
                scores,
                key=lambda symbol: scores[symbol],
                reverse=selection.get("rank_order", "desc") == "desc",
            )
            selected = ordered[:requested]
        else:
            requested = selection["bottom_n"]
            ordered = sorted(scores, key=lambda symbol: scores[symbol])
            selected = ordered[:requested]

        if len(selected) < requested:
            self.warnings.append(
                f"selection returned {len(selected)} symbols, fewer than requested {requested}"
            )
        if not selected:
            return {}

        weight = 1.0 / len(selected)
        return {symbol: weight for symbol in selected}


def _prepare_bars(bars: Any, date: str) -> pd.DataFrame:
    if bars is None:
        return pd.DataFrame(columns=["date", "symbol", "open", "high", "low", "close", "volume"])
    frame = pd.DataFrame(bars).copy()
    if frame.empty:
        return pd.DataFrame(columns=["date", "symbol", "open", "high", "low", "close", "volume"])
    frame["date"] = pd.to_datetime(frame["date"])
    frame["symbol"] = frame["symbol"].map(normalize_symbol)
    frame = frame[frame["date"] <= pd.Timestamp(date)]
    return frame.sort_values(["symbol", "date"]).reset_index(drop=True)


def _resolve_universe(universe: dict[str, Any], bars: pd.DataFrame) -> list[str]:
    if universe.get("symbols"):
        return universe["symbols"]
    return sorted(bars["symbol"].dropna().unique().tolist())


def _is_holding(portfolio_state: PortfolioState, symbol: str) -> bool:
    return (
        portfolio_state.weights.get(symbol, 0.0) > 0
        or portfolio_state.positions.get(symbol, 0.0) > 0
    )


def _stop_loss_triggered(
    risk: dict[str, Any], symbol_bars: pd.DataFrame, portfolio_state: PortfolioState
) -> bool:
    stop_loss = risk.get("stop_loss")
    if stop_loss is None:
        return False
    symbol = symbol_bars["symbol"].iloc[-1]
    entry_price = portfolio_state.entry_price.get(symbol)
    if entry_price is None or entry_price <= 0:
        return False
    current_close = float(symbol_bars["close"].iloc[-1])
    return current_close <= entry_price * (1 - float(stop_loss))


def _evaluate_rule(rule: dict[str, Any], symbol_bars: pd.DataFrame) -> bool:
    op = rule["op"]
    if op == "breakout_high":
        return _breakout_high(rule, symbol_bars)
    if op == "breakdown_low":
        return _breakdown_low(rule, symbol_bars)

    lhs_current, lhs_previous = _current_previous(rule["lhs"], symbol_bars)
    rhs_current, rhs_previous = _current_previous(rule["rhs"], symbol_bars)
    if pd.isna(lhs_current) or pd.isna(rhs_current):
        return False

    if op == ">":
        return lhs_current > rhs_current
    if op == "<":
        return lhs_current < rhs_current
    if op == ">=":
        return lhs_current >= rhs_current
    if op == "<=":
        return lhs_current <= rhs_current
    if pd.isna(lhs_previous) or pd.isna(rhs_previous):
        return False
    if op == "cross_above":
        return lhs_previous <= rhs_previous and lhs_current > rhs_current
    if op == "cross_below":
        return lhs_previous >= rhs_previous and lhs_current < rhs_current
    raise ValidationError(f"unsupported operator: {op!r}")


def _current_previous(expression: dict[str, Any], symbol_bars: pd.DataFrame) -> tuple[float, float]:
    if "value" in expression:
        value = float(expression["value"])
        return value, value
    values = _expression_series(expression, symbol_bars)
    if values.empty:
        return float("nan"), float("nan")
    current = float(values.iloc[-1])
    previous = float(values.iloc[-2]) if len(values) > 1 else float("nan")
    return current, previous


def _expression_series(expression: dict[str, Any], symbol_bars: pd.DataFrame) -> pd.Series:
    result = calculate_indicator(
        symbol_bars, expression["indicator"], expression.get("params", [])
    )
    if isinstance(result, pd.DataFrame):
        return result.iloc[:, 0]
    return result


def _breakout_high(rule: dict[str, Any], symbol_bars: pd.DataFrame) -> bool:
    lookback = _lookback_from_rhs(rule["rhs"])
    if len(symbol_bars) <= lookback:
        return False
    lhs_current, _ = _current_previous(rule["lhs"], symbol_bars)
    previous_high = symbol_bars["close"].iloc[-lookback - 1 : -1].max()
    return lhs_current > float(previous_high)


def _breakdown_low(rule: dict[str, Any], symbol_bars: pd.DataFrame) -> bool:
    lookback = _lookback_from_rhs(rule["rhs"])
    if len(symbol_bars) <= lookback:
        return False
    lhs_current, _ = _current_previous(rule["lhs"], symbol_bars)
    previous_low = symbol_bars["close"].iloc[-lookback - 1 : -1].min()
    return lhs_current < float(previous_low)


def _lookback_from_rhs(rhs: dict[str, Any]) -> int:
    if "value" in rhs:
        return int(rhs["value"])
    params = rhs.get("params", [])
    return int(params[0]) if params else 20


def _score_symbols(
    symbols: list[str], bars: pd.DataFrame, score: dict[str, Any]
) -> dict[str, float]:
    scored: dict[str, float] = {}
    for symbol in symbols:
        symbol_bars = bars[bars["symbol"] == symbol]
        values = calculate_indicator(
            symbol_bars, score["factor"], score.get("params", [])
        )
        if isinstance(values, pd.DataFrame):
            series = values.iloc[:, 0]
        else:
            series = values
        if series.empty or pd.isna(series.iloc[-1]):
            continue
        scored[symbol] = float(series.iloc[-1])
    return scored


def _is_rebalance_day(freq: str, date: str, bars: pd.DataFrame) -> bool:
    if freq == "daily":
        return True
    if bars.empty:
        return False
    current = pd.Timestamp(date)
    prior_dates = sorted(set(bars.loc[bars["date"] < current, "date"]))
    if not prior_dates:
        return True
    previous = pd.Timestamp(prior_dates[-1])
    if freq == "monthly":
        return previous.to_period("M") != current.to_period("M")
    if freq == "weekly":
        return previous.isocalendar()[:2] != current.isocalendar()[:2]
    return False
