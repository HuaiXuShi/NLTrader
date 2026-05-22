import pandas as pd


def sma(bars: pd.DataFrame, window: int) -> pd.Series:
    return _by_symbol(bars, lambda group: group["close"].rolling(window).mean())


SMA = sma


def ema(bars: pd.DataFrame, window: int) -> pd.Series:
    return _by_symbol(
        bars, lambda group: group["close"].ewm(span=window, adjust=False).mean()
    )


EMA = ema


def rsi(bars: pd.DataFrame, window: int = 14) -> pd.Series:
    def calculate(group: pd.DataFrame) -> pd.Series:
        delta = group["close"].diff()
        gain = delta.clip(lower=0).rolling(window).mean()
        loss = (-delta.clip(upper=0)).rolling(window).mean()
        rs = gain / loss
        values = 100 - (100 / (1 + rs))
        return values.mask((loss == 0) & (gain > 0), 100.0)

    return _by_symbol(bars, calculate)


RSI = rsi


def macd(
    bars: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    fast_ema = ema(bars, fast)
    slow_ema = ema(bars, slow)
    macd_line = fast_ema - slow_ema
    signal_line = _by_symbol(
        bars.assign(_macd=macd_line),
        lambda group: group["_macd"].ewm(span=signal, adjust=False).mean(),
    )
    return pd.DataFrame(
        {
            "macd": macd_line,
            "signal": signal_line,
            "hist": macd_line - signal_line,
        },
        index=bars.index,
    )


MACD = macd


def boll_upper(bars: pd.DataFrame, window: int = 20, num_std: float = 2.0) -> pd.Series:
    mean = sma(bars, window)
    std = _by_symbol(bars, lambda group: group["close"].rolling(window).std())
    return mean + num_std * std


BOLL_UPPER = boll_upper


def boll_lower(bars: pd.DataFrame, window: int = 20, num_std: float = 2.0) -> pd.Series:
    mean = sma(bars, window)
    std = _by_symbol(bars, lambda group: group["close"].rolling(window).std())
    return mean - num_std * std


BOLL_LOWER = boll_lower


def return_n(bars: pd.DataFrame, window: int) -> pd.Series:
    return _by_symbol(bars, lambda group: group["close"].pct_change(window))


RETURN_N = return_n


def vol_ma_ratio(bars: pd.DataFrame, window: int) -> pd.Series:
    volume_ma = _by_symbol(bars, lambda group: group["volume"].rolling(window).mean())
    return bars["volume"].astype(float) / volume_ma


VOL_MA_RATIO = vol_ma_ratio


def sma_gap(bars: pd.DataFrame, short_window: int, long_window: int) -> pd.Series:
    short = sma(bars, short_window)
    long = sma(bars, long_window)
    return (short / long) - 1.0


SMA_GAP = sma_gap


def close(bars: pd.DataFrame) -> pd.Series:
    _require_columns(bars, {"close"})
    return bars["close"].astype(float)


def calculate_indicator(
    bars: pd.DataFrame, indicator: str, params: list[object] | None = None
) -> pd.Series | pd.DataFrame:
    params = params or []
    if indicator == "CLOSE":
        return close(bars)
    if indicator == "SMA":
        return sma(bars, int(params[0]))
    if indicator == "EMA":
        return ema(bars, int(params[0]))
    if indicator == "RSI":
        return rsi(bars, int(params[0]) if params else 14)
    if indicator == "MACD":
        values = [12, 26, 9]
        values[: len(params)] = [int(value) for value in params]
        return macd(bars, values[0], values[1], values[2])
    if indicator == "BOLL_UPPER":
        return boll_upper(bars, int(params[0]) if params else 20)
    if indicator == "BOLL_LOWER":
        return boll_lower(bars, int(params[0]) if params else 20)
    if indicator == "RETURN_N":
        return return_n(bars, int(params[0]))
    if indicator == "VOL_MA_RATIO":
        return vol_ma_ratio(bars, int(params[0]))
    if indicator == "SMA_GAP":
        return sma_gap(bars, int(params[0]), int(params[1]))
    raise ValueError(f"unsupported indicator: {indicator!r}")


def _by_symbol(bars: pd.DataFrame, func) -> pd.Series:
    _require_columns(bars, {"date", "symbol", "close"})
    prepared = bars.copy()
    prepared["date"] = pd.to_datetime(prepared["date"])
    output = pd.Series(index=bars.index, dtype="float64")
    for _, group in prepared.sort_values(["symbol", "date"]).groupby(
        "symbol", sort=False
    ):
        values = func(group)
        output.loc[group.index] = values.to_numpy()
    return output


def _require_columns(bars: pd.DataFrame, columns: set[str]) -> None:
    missing = columns - set(bars.columns)
    if missing:
        raise ValueError(f"bars missing required columns: {sorted(missing)}")
