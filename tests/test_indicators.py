import math

import pandas as pd

from src.indicators import (
    BOLL_LOWER,
    BOLL_UPPER,
    MACD,
    ema,
    return_n,
    rsi,
    sma,
    sma_gap,
    vol_ma_ratio,
)


def _bars(closes, volumes=None, symbol="SH600036"):
    if volumes is None:
        volumes = [1000.0] * len(closes)
    return pd.DataFrame(
        {
            "date": pd.date_range("2021-01-01", periods=len(closes), freq="D"),
            "symbol": symbol,
            "close": [float(value) for value in closes],
            "volume": [float(value) for value in volumes],
        }
    )


def test_sma_returns_rolling_close_average_by_symbol():
    values = sma(_bars([1, 2, 3, 4]), 3)

    assert math.isnan(values.iloc[1])
    assert values.iloc[2] == 2.0
    assert values.iloc[3] == 3.0


def test_sma_handles_interleaved_unsorted_symbols_and_preserves_input_index():
    bars = pd.DataFrame(
        {
            "date": [
                "2021-01-02",
                "2021-01-01",
                "2021-01-01",
                "2021-01-02",
            ],
            "symbol": ["SH600036", "SZ000001", "SH600036", "SZ000001"],
            "close": [3.0, 10.0, 1.0, 14.0],
            "volume": [100.0, 100.0, 100.0, 100.0],
        },
        index=[10, 20, 30, 40],
    )

    values = sma(bars, 2)

    assert list(values.index) == [10, 20, 30, 40]
    assert values.loc[10] == 2.0
    assert math.isnan(values.loc[20])
    assert math.isnan(values.loc[30])
    assert values.loc[40] == 12.0


def test_ema_matches_pandas_span_adjust_false():
    bars = _bars([1, 2, 3, 4])

    values = ema(bars, 3)

    expected = bars["close"].ewm(span=3, adjust=False).mean()
    pd.testing.assert_series_equal(values, expected, check_names=False)


def test_rsi_reaches_100_when_window_has_only_gains():
    values = rsi(_bars([1, 2, 3, 4, 5]), 3)

    assert math.isnan(values.iloc[2])
    assert values.iloc[3] == 100.0
    assert values.iloc[4] == 100.0


def test_return_n_computes_percent_return_by_symbol():
    values = return_n(_bars([10, 12, 15]), 2)

    assert math.isnan(values.iloc[1])
    assert values.iloc[2] == 0.5


def test_vol_ma_ratio_divides_volume_by_rolling_average_volume():
    values = vol_ma_ratio(_bars([10, 10, 10], volumes=[100, 200, 300]), 2)

    assert math.isnan(values.iloc[0])
    assert values.iloc[1] == 200 / 150
    assert values.iloc[2] == 300 / 250


def test_sma_gap_computes_short_minus_long_relative_gap():
    values = sma_gap(_bars([1, 2, 3, 4]), 2, 3)

    assert math.isnan(values.iloc[1])
    assert values.iloc[2] == (2.5 / 2.0) - 1.0
    assert values.iloc[3] == (3.5 / 3.0) - 1.0


def test_macd_returns_line_signal_and_histogram_frame():
    values = MACD(_bars([1, 2, 3, 4]), 2, 3, 2)

    assert list(values.columns) == ["macd", "signal", "hist"]
    assert values["hist"].iloc[-1] == values["macd"].iloc[-1] - values["signal"].iloc[-1]


def test_boll_upper_and_lower_match_rolling_mean_plus_minus_std():
    bars = _bars([1, 2, 3])

    upper = BOLL_UPPER(bars, 3)
    lower = BOLL_LOWER(bars, 3)

    assert upper.iloc[-1] == 2.0 + 1.0 * 2.0
    assert lower.iloc[-1] == 2.0 - 1.0 * 2.0
