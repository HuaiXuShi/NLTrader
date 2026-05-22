from __future__ import annotations

from typing import Any

import pandas as pd

from src.models import BacktestResult


def map_qlib_result(
    qlib_report: Any,
    qlib_positions: Any,
    qlib_analysis: dict[str, Any] | Any | None,
    capability_summary: dict[str, Any],
    strategy_summary: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
) -> BacktestResult:
    analysis = _analysis_dict(qlib_analysis)
    equity_curve = _equity_curve(qlib_report)
    metrics = _metrics(qlib_report, analysis, qlib_positions)

    return BacktestResult(
        strategy_summary=strategy_summary or {},
        capability_summary=capability_summary,
        qlib_report=qlib_report,
        qlib_positions=qlib_positions,
        qlib_analysis=analysis,
        equity_curve=equity_curve,
        positions_history=qlib_positions,
        metrics=metrics,
        warnings=warnings or [],
    )


def _analysis_dict(analysis: dict[str, Any] | Any | None) -> dict[str, Any]:
    if analysis is None:
        return {}
    if isinstance(analysis, dict):
        return dict(analysis)
    if isinstance(analysis, pd.Series):
        return analysis.dropna().to_dict()
    if isinstance(analysis, pd.DataFrame):
        if len(analysis.columns) == 1:
            return analysis.iloc[:, 0].dropna().to_dict()
        return analysis.dropna(how="all").to_dict()
    return {}


def _equity_curve(report: Any) -> pd.DataFrame | None:
    frame = _as_frame(report)
    if frame is None or "return" not in frame.columns:
        return None

    equity = (1.0 + frame["return"].fillna(0.0).astype(float)).cumprod()
    result = pd.DataFrame({"equity": equity}, index=frame.index)
    if "bench" in frame.columns:
        result["benchmark_equity"] = (
            1.0 + frame["bench"].fillna(0.0).astype(float)
        ).cumprod()
    if "cost" in frame.columns:
        result["cost"] = frame["cost"]
    return result


def _metrics(
    report: Any, analysis: dict[str, Any], positions: Any
) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    frame = _as_frame(report)
    if frame is not None:
        if "return" in frame.columns:
            metrics["total_return"] = float(
                (1.0 + frame["return"].fillna(0.0).astype(float)).prod() - 1.0
            )
        if "turnover" in frame.columns:
            metrics["turnover"] = float(frame["turnover"].fillna(0.0).astype(float).sum())

    for key in (
        "return",
        "annualized_return",
        "max_drawdown",
        "information_ratio",
        "sharpe",
    ):
        if key in analysis:
            metrics[key] = _to_float_if_numeric(analysis[key])

    metrics.setdefault("num_trades", _num_trades(positions))
    return metrics


def _as_frame(value: Any) -> pd.DataFrame | None:
    if value is None:
        return None
    if isinstance(value, pd.DataFrame):
        return value
    if isinstance(value, pd.Series):
        return value.to_frame()
    if isinstance(value, dict):
        return None
    return pd.DataFrame(value)


def _num_trades(positions: Any) -> int:
    frame = _as_frame(positions)
    if frame is None or frame.empty:
        return 0
    if "trade" in frame.columns:
        return int(frame["trade"].fillna(0).astype(bool).sum())
    if "amount" in frame.columns:
        return int((frame["amount"].fillna(0) != 0).sum())
    return 0


def _to_float_if_numeric(value: Any) -> Any:
    try:
        return float(value)
    except (TypeError, ValueError):
        return value
