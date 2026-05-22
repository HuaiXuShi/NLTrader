from typing import Protocol

import pandas as pd

from src.models import UniverseSpec


class DataProviderError(RuntimeError):
    pass


class DataProvider(Protocol):
    def get_capabilities(self) -> dict[str, object]:
        ...

    def get_calendar(self, start: str, end: str) -> pd.DataFrame:
        ...

    def get_bars(
        self,
        symbols: list[str],
        start: str,
        end: str,
        fields: list[str] | None = None,
    ) -> pd.DataFrame:
        ...

    def resolve_universe(
        self, universe_spec: UniverseSpec, start: str, end: str
    ) -> list[str]:
        ...
