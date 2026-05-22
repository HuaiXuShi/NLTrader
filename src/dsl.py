from collections.abc import Mapping
from typing import Any

from src.symbols import normalize_symbol


SUPPORTED_STRATEGY_KINDS = frozenset({"timeseries", "cross_sectional"})
SUPPORTED_MARKETS = frozenset({"CN_A"})
SUPPORTED_FREQUENCIES = frozenset({"D"})
SUPPORTED_UNIVERSE_TYPES = frozenset(
    {"single_symbol", "symbol_list", "preset_pool", "uploaded_pool"}
)
SUPPORTED_REBALANCE_FREQUENCIES = frozenset({"daily", "weekly", "monthly"})
SUPPORTED_RANK_ORDERS = frozenset({"asc", "desc"})
SUPPORTED_INDICATORS = frozenset(
    {
        "SMA",
        "EMA",
        "RSI",
        "MACD",
        "BOLL_UPPER",
        "BOLL_LOWER",
        "RETURN_N",
        "VOL_MA_RATIO",
        "CLOSE",
    }
)
SUPPORTED_SCORE_FACTORS = frozenset({"RETURN_N", "RSI", "SMA_GAP", "VOL_MA_RATIO"})
SUPPORTED_OPERATORS = frozenset(
    {
        ">",
        "<",
        ">=",
        "<=",
        "cross_above",
        "cross_below",
        "breakout_high",
        "breakdown_low",
    }
)
ONE_PARAM_INDICATORS = frozenset(
    {"SMA", "EMA", "RSI", "BOLL_UPPER", "BOLL_LOWER", "RETURN_N", "VOL_MA_RATIO"}
)
ONE_PARAM_SCORE_FACTORS = frozenset({"RETURN_N", "RSI", "VOL_MA_RATIO"})


class ValidationError(ValueError):
    pass


def validate_dsl(dsl: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(dsl, Mapping):
        raise ValidationError("dsl must be a mapping")

    validated = dict(dsl)
    strategy_kind = _require_supported(
        validated, "strategy_kind", SUPPORTED_STRATEGY_KINDS, "strategy_kind"
    )
    _require_supported(validated, "market", SUPPORTED_MARKETS, "market")
    _require_supported(validated, "frequency", SUPPORTED_FREQUENCIES, "frequency")
    _validate_rebalance(validated.get("rebalance", {}))

    if "risk" in validated:
        validated["risk"] = _validate_risk(validated["risk"])

    if "universe" in validated:
        validated["universe"] = validate_universe(validated["universe"])

    if strategy_kind == "timeseries":
        _validate_timeseries(validated)
    elif strategy_kind == "cross_sectional":
        _validate_cross_sectional(validated)

    return validated


def validate_universe(universe: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(universe, Mapping):
        raise ValidationError("universe must be a mapping")

    validated = dict(universe)
    universe_type = _require_supported(
        validated, "type", SUPPORTED_UNIVERSE_TYPES, "universe type"
    )

    symbols = validated.get("symbols", [])
    if symbols:
        if not isinstance(symbols, list):
            raise ValidationError("universe symbols must be a list")
        validated["symbols"] = [
            _normalize_symbol_or_raise(symbol, "universe symbol") for symbol in symbols
        ]

    if universe_type in {"single_symbol", "symbol_list", "uploaded_pool"}:
        if not validated.get("symbols"):
            raise ValidationError(f"{universe_type} universe requires symbols")

    if universe_type == "preset_pool" and not (
        validated.get("pool_name") or validated.get("qlib_market")
    ):
        raise ValidationError("preset_pool universe requires pool_name or qlib_market")

    return validated


def validate_target_weights(weights: Mapping[str, float]) -> dict[str, float]:
    if not isinstance(weights, Mapping):
        raise ValidationError("weights must be a mapping")

    normalized: dict[str, float] = {}
    for raw_symbol, raw_weight in weights.items():
        symbol = _normalize_symbol_or_raise(raw_symbol, "target weight symbol")
        try:
            weight = float(raw_weight)
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"weight for {raw_symbol!r} must be numeric") from exc
        if weight < 0:
            raise ValidationError("target weights must be long-only")
        normalized[symbol] = weight

    if sum(normalized.values()) > 1.0 + 1e-12:
        raise ValidationError("target weights sum must be at most 1")

    return normalized


def _validate_timeseries(dsl: Mapping[str, Any]) -> None:
    if "universe" not in dsl:
        raise ValidationError("timeseries strategy requires universe")

    signal = dsl.get("signal", {})
    if not isinstance(signal, Mapping):
        raise ValidationError("timeseries signal must be a mapping")

    entry_rules = signal.get("entry_rules", [])
    exit_rules = signal.get("exit_rules", [])
    if not entry_rules and not exit_rules:
        raise ValidationError("timeseries strategy requires at least one entry or exit rule")

    _validate_rules(entry_rules, "signal.entry_rules")
    _validate_rules(exit_rules, "signal.exit_rules")


def _validate_cross_sectional(dsl: Mapping[str, Any]) -> None:
    if "universe" not in dsl:
        raise ValidationError("cross_sectional strategy requires universe")

    selection = dsl.get("selection", {})
    if not isinstance(selection, Mapping):
        raise ValidationError("cross_sectional selection must be a mapping")

    _validate_rules(selection.get("filters", []), "selection.filters")
    _validate_score(selection.get("score", {}))
    if "rank_order" in selection and selection["rank_order"] not in SUPPORTED_RANK_ORDERS:
        raise ValidationError("selection.rank_order must be asc or desc")
    _validate_construction(dsl.get("construction"))

    selection_count_fields = []
    for field in ("top_n", "bottom_n"):
        if field in selection:
            value = selection[field]
            if not isinstance(value, int) or value <= 0:
                raise ValidationError(f"{field} must be > 0")
            selection_count_fields.append(field)

    if len(selection_count_fields) != 1:
        raise ValidationError("cross_sectional selection requires positive top_n or bottom_n")


def _validate_rules(rules: Any, path: str) -> None:
    if not isinstance(rules, list):
        raise ValidationError(f"{path} must be a list")

    for index, rule in enumerate(rules):
        if not isinstance(rule, Mapping):
            raise ValidationError(f"{path}[{index}] must be a mapping")
        _require_supported(rule, "op", SUPPORTED_OPERATORS, "operator")
        _validate_expression(rule.get("lhs"), f"{path}[{index}].lhs")
        _validate_expression(rule.get("rhs"), f"{path}[{index}].rhs")


def _validate_score(score: Any) -> None:
    if not score:
        raise ValidationError("selection.score is required")
    if not isinstance(score, Mapping):
        raise ValidationError("selection.score must be a mapping")
    factor = score.get("factor")
    if factor not in SUPPORTED_SCORE_FACTORS:
        raise ValidationError(f"unsupported indicator: {factor!r}")
    _validate_params(factor, score.get("params", []), "selection.score.params")


def _validate_construction(construction: Any) -> None:
    if not isinstance(construction, Mapping):
        raise ValidationError("cross_sectional construction is required")
    if construction.get("weighting") != "equal_weight":
        raise ValidationError("unsupported construction weighting")


def _validate_expression(expression: Any, path: str) -> None:
    if not isinstance(expression, Mapping):
        raise ValidationError(f"{path} must be a mapping")

    if "indicator" in expression:
        indicator = expression["indicator"]
        if indicator not in SUPPORTED_INDICATORS:
            raise ValidationError(f"unsupported indicator: {indicator!r}")
        _validate_params(indicator, expression.get("params", []), f"{path}.params")
        return

    if "value" in expression:
        return

    raise ValidationError(f"{path} requires indicator or value")


def _validate_params(name: str, params: Any, path: str) -> None:
    if not isinstance(params, list):
        raise ValidationError(f"{path} must be a list")

    for index, value in enumerate(params):
        if not _is_positive_int(value):
            raise ValidationError(f"{path}[{index}] must be a positive integer")

    if name == "CLOSE":
        _require_param_count(name, params, {0}, path)
    elif name in ONE_PARAM_INDICATORS or name in ONE_PARAM_SCORE_FACTORS:
        _require_param_count(name, params, {1}, path)
    elif name == "MACD":
        _require_param_count(name, params, {0, 3}, path)
    elif name == "SMA_GAP":
        _require_param_count(name, params, {2}, path)


def _require_param_count(
    name: str, params: list[Any], allowed_counts: set[int], path: str
) -> None:
    if len(params) not in allowed_counts:
        expected = " or ".join(str(count) for count in sorted(allowed_counts))
        raise ValidationError(f"{path} for {name} must contain {expected} values")


def _is_positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _validate_rebalance(rebalance: Any) -> None:
    if not rebalance:
        return
    if not isinstance(rebalance, Mapping):
        raise ValidationError("rebalance must be a mapping")
    _require_supported(
        rebalance, "freq", SUPPORTED_REBALANCE_FREQUENCIES, "rebalance frequency"
    )


def _validate_risk(risk: Any) -> dict[str, Any]:
    if not isinstance(risk, Mapping):
        raise ValidationError("risk must be a mapping")

    validated = dict(risk)
    unknown = set(validated) - {"stop_loss"}
    if unknown:
        raise ValidationError(f"unsupported risk fields: {sorted(unknown)}")

    if "stop_loss" not in validated or validated["stop_loss"] is None:
        return validated

    stop_loss = validated["stop_loss"]
    if isinstance(stop_loss, bool) or not isinstance(stop_loss, (int, float)):
        raise ValidationError("risk.stop_loss must be a numeric ratio")

    stop_loss_float = float(stop_loss)
    if not 0 < stop_loss_float < 1:
        raise ValidationError("risk.stop_loss must be between 0 and 1")

    validated["stop_loss"] = stop_loss_float
    return validated


def _require_supported(
    data: Mapping[str, Any], field: str, supported: frozenset[str], label: str
) -> str:
    value = data.get(field)
    if value not in supported:
        raise ValidationError(f"unsupported {label}: {value!r}")
    return value


def _normalize_symbol_or_raise(symbol: object, context: str) -> str:
    try:
        return normalize_symbol(symbol)
    except ValueError as exc:
        raise ValidationError(f"invalid {context}: {symbol!r}") from exc
