from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.compiler import compile_strategy
from src.data_provider import DataProviderError
from src.dsl import ValidationError, validate_dsl
from src.models import BacktestResult, ParseResult, UniverseSpec
from src.parser import parse_strategy
from src.qlib_evaluator import QlibEvaluator
from src.qlib_provider import QlibDataProvider


class PipelineResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    parse_result: ParseResult
    compiled_strategy: Any | None = None
    backtest_result: BacktestResult | None = None
    status: str
    warnings: list[str] = Field(default_factory=list)


def run_backtest_pipeline(
    text: str,
    start: str,
    end: str,
    data_provider: Any | None = None,
    evaluator: Any | None = None,
    parser: Any | None = None,
    fallback: bool = True,
) -> PipelineResult:
    try:
        parse_result = _parse(text, parser, fallback)
    except ValidationError as exc:
        parse_result = ParseResult(dsl={}, strategy_kind="unsupported")
        return PipelineResult(
            parse_result=parse_result,
            status="validation_error",
            warnings=[str(exc)],
        )
    warnings = list(parse_result.warnings)

    if parse_result.strategy_kind == "unsupported" or not parse_result.dsl:
        return PipelineResult(
            parse_result=parse_result,
            status="unsupported",
            warnings=_with_warning(warnings, "Strategy is unsupported or has no DSL."),
        )

    try:
        dsl = validate_dsl(parse_result.dsl)
        parse_result.dsl = dsl
        universe_spec = _universe_spec_from_dsl(dsl)
        compiled_strategy = compile_strategy(dsl)
        runner = evaluator or _default_evaluator(data_provider)
        backtest_result = runner.run(compiled_strategy, universe_spec, start, end)
    except ValidationError as exc:
        return PipelineResult(
            parse_result=parse_result,
            status="validation_error",
            warnings=_with_warning(warnings, str(exc)),
        )
    except DataProviderError as exc:
        return PipelineResult(
            parse_result=parse_result,
            status="data_error",
            warnings=_with_warning(warnings, str(exc)),
        )

    warnings.extend(getattr(compiled_strategy, "warnings", []))
    warnings.extend(backtest_result.warnings)
    return PipelineResult(
        parse_result=parse_result,
        compiled_strategy=compiled_strategy,
        backtest_result=backtest_result,
        status="ok",
        warnings=warnings,
    )


def _parse(text: str, parser: Any | None, fallback: bool) -> ParseResult:
    if parser is None:
        return parse_strategy(text, fallback=fallback)
    parse = getattr(parser, "parse", None)
    if callable(parse):
        return parse(text, fallback=fallback)
    if callable(parser):
        return parser(text, fallback=fallback)
    raise TypeError("parser must be callable or expose parse(text, fallback=...)")


def _default_evaluator(data_provider: Any | None) -> QlibEvaluator:
    provider = data_provider or QlibDataProvider()
    return QlibEvaluator(provider)


def _universe_spec_from_dsl(dsl: dict[str, Any]) -> UniverseSpec:
    universe = dsl.get("universe")
    if not isinstance(universe, dict):
        raise ValidationError("strategy requires explicit universe")
    return UniverseSpec(
        type=universe["type"],
        symbols=list(universe.get("symbols", [])),
        pool_name=universe.get("pool_name"),
        qlib_market=universe.get("qlib_market"),
    )


def _with_warning(warnings: list[str], warning: str) -> list[str]:
    if warning and warning not in warnings:
        return warnings + [warning]
    return warnings
