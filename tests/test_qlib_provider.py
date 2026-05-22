import sys
from types import SimpleNamespace

import pandas as pd
import pytest

from src.data_provider import DataProviderError
from src.models import UniverseSpec
from src.qlib_provider import QlibDataProvider


class FakeD:
    def __init__(self):
        self.feature_calls = []
        self.instrument_calls = []
        self.list_instrument_calls = []

    def calendar(self, start_time=None, end_time=None, freq="day"):
        assert freq == "day"
        assert start_time == "2021-01-01"
        assert end_time == "2021-01-05"
        return pd.to_datetime(["2021-01-04", "2021-01-05"])

    def features(self, instruments, fields, start_time=None, end_time=None, freq="day"):
        self.feature_calls.append(
            {
                "instruments": instruments,
                "fields": fields,
                "start_time": start_time,
                "end_time": end_time,
                "freq": freq,
            }
        )
        index = pd.MultiIndex.from_tuples(
            [
                ("SH600036", pd.Timestamp("2021-01-04")),
                ("SZ000001", pd.Timestamp("2021-01-04")),
            ],
            names=["instrument", "datetime"],
        )
        return pd.DataFrame(
            {
                "$open": [10.0, 20.0],
                "$high": [11.0, 21.0],
                "$low": [9.0, 19.0],
                "$close": [10.5, 20.5],
                "$volume": [1000.0, 2000.0],
            },
            index=index,
        )

    def instruments(self, market):
        self.instrument_calls.append(market)
        return f"INSTRUMENTS:{market}"

    def list_instruments(self, instruments, start_time=None, end_time=None, as_list=True):
        self.list_instrument_calls.append(
            {
                "instruments": instruments,
                "start_time": start_time,
                "end_time": end_time,
                "as_list": as_list,
            }
        )
        return ["SH600036", "sz000001"]


@pytest.fixture
def fake_qlib(monkeypatch):
    fake_d = FakeD()
    init_calls = []
    fake_qlib_module = SimpleNamespace(
        init=lambda **kwargs: init_calls.append(kwargs),
        constant=SimpleNamespace(REG_CN="cn"),
        data=SimpleNamespace(D=fake_d),
    )
    monkeypatch.setitem(sys.modules, "qlib", fake_qlib_module)
    monkeypatch.setitem(sys.modules, "qlib.constant", fake_qlib_module.constant)
    monkeypatch.setitem(sys.modules, "qlib.data", fake_qlib_module.data)
    return fake_d, init_calls


def test_missing_provider_uri_raises_readable_data_provider_error(tmp_path):
    missing_path = tmp_path / "missing"

    with pytest.raises(DataProviderError) as exc_info:
        QlibDataProvider(provider_uri=str(missing_path))

    message = str(exc_info.value)
    assert str(missing_path) in message
    assert "prepare_qlib_data.md" in message
    assert "Traceback" not in message


def test_real_pyqlib_importable_and_missing_path_error_needs_no_monkeypatch(tmp_path):
    import qlib

    assert qlib is not None
    missing_path = tmp_path / "missing-real-qlib"

    with pytest.raises(DataProviderError) as exc_info:
        QlibDataProvider(provider_uri=str(missing_path))

    message = str(exc_info.value)
    assert str(missing_path) in message
    assert "prepare_qlib_data.md" in message
    assert "Traceback" not in message


def test_get_calendar_returns_normalized_calendar_frame(tmp_path, fake_qlib):
    _, init_calls = fake_qlib
    provider = QlibDataProvider(provider_uri=str(tmp_path), region="cn")

    frame = provider.get_calendar("2021-01-01", "2021-01-05")

    assert list(frame.columns) == ["date", "is_open"]
    assert frame["date"].tolist() == [
        pd.Timestamp("2021-01-04"),
        pd.Timestamp("2021-01-05"),
    ]
    assert frame["is_open"].tolist() == [True, True]
    assert init_calls == [{"provider_uri": str(tmp_path), "region": "cn"}]


def test_get_bars_normalizes_symbols_and_qlib_fields(tmp_path, fake_qlib):
    fake_d, _ = fake_qlib
    provider = QlibDataProvider(provider_uri=str(tmp_path))

    frame = provider.get_bars(["600036.SH", "000001.sz"], "2021-01-01", "2021-01-05")

    assert fake_d.feature_calls[0]["instruments"] == ["SH600036", "SZ000001"]
    assert fake_d.feature_calls[0]["fields"] == [
        "$open",
        "$high",
        "$low",
        "$close",
        "$volume",
    ]
    assert list(frame.columns) == [
        "date",
        "symbol",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "amount",
    ]
    assert frame["symbol"].tolist() == ["SH600036", "SZ000001"]
    assert frame["amount"].isna().all()
    assert frame.loc[0, "close"] == 10.5


def test_get_bars_honors_custom_fields_and_keeps_required_output_columns(
    tmp_path, fake_qlib
):
    fake_d, _ = fake_qlib
    provider = QlibDataProvider(provider_uri=str(tmp_path))

    frame = provider.get_bars(["SH600036"], "2021-01-01", "2021-01-05", fields=["$close"])

    assert fake_d.feature_calls[0]["fields"] == ["$close"]
    assert list(frame.columns) == [
        "date",
        "symbol",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "amount",
    ]


@pytest.mark.parametrize(
    ("universe", "expected"),
    [
        (UniverseSpec(type="single_symbol", symbols=["600036.SH"]), ["SH600036"]),
        (
            UniverseSpec(type="symbol_list", symbols=["600036.SH", "000001.SZ"]),
            ["SH600036", "SZ000001"],
        ),
        (
            UniverseSpec(type="uploaded_pool", symbols=["sh600036", "sz000001"]),
            ["SH600036", "SZ000001"],
        ),
    ],
)
def test_resolve_universe_normalizes_explicit_symbol_specs(
    tmp_path, fake_qlib, universe, expected
):
    provider = QlibDataProvider(provider_uri=str(tmp_path))

    assert provider.resolve_universe(universe, "2021-01-01", "2021-01-05") == expected


def test_resolve_universe_maps_preset_pool_to_qlib_instruments(tmp_path, fake_qlib):
    fake_d, _ = fake_qlib
    provider = QlibDataProvider(provider_uri=str(tmp_path))
    universe = UniverseSpec(type="preset_pool", pool_name="CSI300")

    symbols = provider.resolve_universe(universe, "2021-01-01", "2021-01-05")

    assert symbols == ["SH600036", "SZ000001"]
    assert fake_d.instrument_calls == ["csi300"]
    assert fake_d.list_instrument_calls[0]["start_time"] == "2021-01-01"
    assert fake_d.list_instrument_calls[0]["end_time"] == "2021-01-05"


def test_get_capabilities_returns_required_summary(tmp_path, fake_qlib):
    provider = QlibDataProvider(
        provider_uri=str(tmp_path), region="cn", benchmark="SH000300"
    )

    capabilities = provider.get_capabilities()

    assert capabilities["provider_name"] == "QlibDataProvider"
    assert capabilities["provider_uri"] == str(tmp_path)
    assert capabilities["region"] == "cn"
    assert capabilities["benchmark"] == "SH000300"
    assert capabilities["has_calendar"] is True
    assert capabilities["has_ohlcv"] is True
    assert capabilities["has_adjusted_prices"] is True
    assert capabilities["has_raw_prices"] is False
    assert capabilities["has_suspend_info"] is False
    assert capabilities["has_limit_prices"] is False
    assert capabilities["has_limit_threshold"] is True
    assert capabilities["has_dynamic_universe_membership"] is True
    assert capabilities["has_benchmark_series"] is True
    assert capabilities["uses_qlib_region_cn"] is True
