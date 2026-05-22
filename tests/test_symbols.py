import pytest

from src.symbols import normalize_symbol


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("SH600036", "SH600036"),
        ("SZ000001", "SZ000001"),
        ("600036.SH", "SH600036"),
        ("000001.SZ", "SZ000001"),
        ("sh600036", "SH600036"),
        ("sz000001", "SZ000001"),
        (" 600036.sh ", "SH600036"),
        (" 000001 ", "SZ000001"),
        ("600036", "SH600036"),
        ("300750", "SZ300750"),
    ],
)
def test_normalize_symbol_accepts_supported_cn_a_formats(raw, expected):
    assert normalize_symbol(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        " ",
        "60003",
        "600036.SS",
        "BJ430047",
        "ABCDEF",
        "SH60003A",
        None,
    ],
)
def test_normalize_symbol_rejects_invalid_symbols(raw):
    with pytest.raises(ValueError):
        normalize_symbol(raw)
