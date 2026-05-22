import re


_PREFIX_PATTERN = re.compile(r"^(SH|SZ)(\d{6})$")
_SUFFIX_PATTERN = re.compile(r"^(\d{6})\.(SH|SZ)$")
_DIGITS_PATTERN = re.compile(r"^\d{6}$")


def normalize_symbol(symbol: object) -> str:
    if not isinstance(symbol, str):
        raise ValueError("symbol must be a string")

    value = symbol.strip().upper()
    if not value:
        raise ValueError("symbol must not be empty")

    prefix_match = _PREFIX_PATTERN.fullmatch(value)
    if prefix_match:
        return f"{prefix_match.group(1)}{prefix_match.group(2)}"

    suffix_match = _SUFFIX_PATTERN.fullmatch(value)
    if suffix_match:
        return f"{suffix_match.group(2)}{suffix_match.group(1)}"

    if _DIGITS_PATTERN.fullmatch(value):
        exchange = "SH" if value.startswith("6") else "SZ"
        return f"{exchange}{value}"

    raise ValueError(f"invalid CN A-share symbol: {symbol!r}")
