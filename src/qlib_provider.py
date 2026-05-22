from pathlib import Path
from typing import Any

import pandas as pd

from src.config import load_settings
from src.data_provider import DataProviderError
from src.models import UniverseSpec
from src.symbols import normalize_symbol


DEFAULT_FIELDS = ["$open", "$high", "$low", "$close", "$volume"]
OUTPUT_COLUMNS = ["date", "symbol", "open", "high", "low", "close", "volume", "amount"]
FIELD_MAP = {
    "$open": "open",
    "$high": "high",
    "$low": "low",
    "$close": "close",
    "$volume": "volume",
    "$amount": "amount",
}


class QlibDataProvider:
    def __init__(
        self,
        provider_uri: str | None = None,
        region: str | None = None,
        benchmark: str | None = None,
    ) -> None:
        settings = load_settings()
        self.provider_uri = provider_uri or settings.qlib_provider_uri
        self.region = region or settings.qlib_region
        self.benchmark = benchmark or settings.qlib_benchmark
        self._provider_path = Path(self.provider_uri).expanduser()
        self._ensure_provider_path()
        self._init_qlib()

    def get_capabilities(self) -> dict[str, object]:
        return {
            "provider_name": "QlibDataProvider",
            "provider_uri": self.provider_uri,
            "region": self.region,
            "benchmark": self.benchmark,
            "has_calendar": True,
            "has_ohlcv": True,
            "has_adjusted_prices": True,
            "has_raw_prices": False,
            "has_suspend_info": False,
            "has_limit_prices": False,
            "has_limit_threshold": True,
            "has_dynamic_universe_membership": True,
            "has_benchmark_series": True,
            "uses_qlib_region_cn": self.region.lower() == "cn",
        }

    def get_calendar(self, start: str, end: str) -> pd.DataFrame:
        dates = self._d().calendar(start_time=start, end_time=end, freq="day")
        return pd.DataFrame({"date": pd.to_datetime(list(dates)), "is_open": True})

    def get_bars(
        self,
        symbols: list[str],
        start: str,
        end: str,
        fields: list[str] | None = None,
    ) -> pd.DataFrame:
        normalized_symbols = [normalize_symbol(symbol) for symbol in symbols]
        qlib_fields = fields or DEFAULT_FIELDS
        raw = self._d().features(
            normalized_symbols,
            qlib_fields,
            start_time=start,
            end_time=end,
            freq="day",
        )
        frame = self._normalize_bars_frame(raw)
        return frame[OUTPUT_COLUMNS]

    def resolve_universe(
        self, universe_spec: UniverseSpec, start: str, end: str
    ) -> list[str]:
        if universe_spec.type in {"single_symbol", "symbol_list", "uploaded_pool"}:
            return [normalize_symbol(symbol) for symbol in universe_spec.symbols]

        if universe_spec.type == "preset_pool":
            market = (universe_spec.qlib_market or universe_spec.pool_name or "").lower()
            if not market:
                raise DataProviderError("preset_pool universe requires qlib_market or pool_name")
            instruments = self._d().instruments(market)
            symbols = self._d().list_instruments(
                instruments,
                start_time=start,
                end_time=end,
                as_list=True,
            )
            return [normalize_symbol(symbol) for symbol in symbols]

        raise DataProviderError(f"unsupported universe type: {universe_spec.type!r}")

    def _ensure_provider_path(self) -> None:
        if self._provider_path.exists():
            return
        raise DataProviderError(
            "Qlib provider_uri does not exist: "
            f"{self._provider_path}. Prepare data first; see scripts/prepare_qlib_data.md "
            "or set QLIB_PROVIDER_URI in .env."
        )

    def _init_qlib(self) -> None:
        try:
            import qlib
            from qlib.constant import REG_CN
        except ImportError as exc:
            raise DataProviderError("Qlib is not installed in the active environment.") from exc

        qlib_region = REG_CN if self.region.lower() == "cn" else self.region
        try:
            qlib.init(provider_uri=str(self._provider_path), region=qlib_region)
        except Exception as exc:
            raise DataProviderError(f"Failed to initialize Qlib data provider: {exc}") from exc

    def _d(self) -> Any:
        from qlib.data import D

        return D

    def _normalize_bars_frame(self, raw: pd.DataFrame) -> pd.DataFrame:
        frame = raw.copy()
        if isinstance(frame.index, pd.MultiIndex):
            frame = frame.reset_index()

        frame = frame.rename(columns=FIELD_MAP)
        frame = frame.rename(
            columns={
                "instrument": "symbol",
                "datetime": "date",
            }
        )

        if "date" not in frame.columns or "symbol" not in frame.columns:
            raise DataProviderError("Qlib features result must include date and symbol index")

        frame["date"] = pd.to_datetime(frame["date"])
        frame["symbol"] = frame["symbol"].map(normalize_symbol)

        for column in OUTPUT_COLUMNS:
            if column not in frame.columns:
                frame[column] = pd.NA

        return frame.sort_values(["date", "symbol"]).reset_index(drop=True)
