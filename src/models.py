from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ParseResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dsl: dict[str, Any]
    strategy_kind: str
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    human_summary: str = ""
    parse_confidence: float = 0.0


class CapabilitySet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    has_calendar: bool = True
    has_ohlcv: bool = True
    has_adjusted_prices: bool = True
    has_raw_prices: bool = False
    has_suspend_info: bool = False
    has_limit_prices: bool = False
    has_limit_threshold: bool = True
    has_dynamic_universe_membership: bool = True
    has_benchmark_series: bool = True
    uses_qlib_region_cn: bool = True


class UniverseSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    symbols: list[str] = Field(default_factory=list)
    pool_name: str | None = None
    qlib_market: str | None = None


class MarketState(BaseModel):
    model_config = ConfigDict(extra="allow")

    date: str
    bars: Any | None = None
    calendar: Any | None = None


class PortfolioState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cash: float = 0.0
    positions: dict[str, float] = Field(default_factory=dict)
    weights: dict[str, float] = Field(default_factory=dict)
    entry_price: dict[str, float] = Field(default_factory=dict)


class BacktestResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    strategy_summary: dict[str, Any] = Field(default_factory=dict)
    capability_summary: dict[str, Any] = Field(default_factory=dict)
    qlib_report: Any | None = None
    qlib_positions: Any | None = None
    qlib_analysis: dict[str, Any] = Field(default_factory=dict)
    equity_curve: Any | None = None
    positions_history: Any | None = None
    trades: Any | None = None
    rebalances: Any | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
