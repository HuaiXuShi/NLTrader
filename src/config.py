from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    llm_api_base: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None
    llm_timeout_seconds: float = 60.0
    llm_temperature: float = 0.0
    qlib_provider_uri: str = "~/.qlib/qlib_data/cn_data"
    qlib_region: str = "cn"
    qlib_benchmark: str = "SH000300"
    qlib_deal_price: str = "close"
    qlib_limit_threshold: float = 0.095
    qlib_open_cost: float = 0.0005
    qlib_close_cost: float = 0.0015
    qlib_min_cost: float = 5.0
    qlib_account: float = 100000000.0


def load_settings(env_path: str | Path = ".env") -> Settings:
    values = _read_dotenv(Path(env_path))
    env = values | os.environ

    return Settings(
        llm_api_base=_optional(env, "LLM_API_BASE"),
        llm_api_key=_optional(env, "LLM_API_KEY"),
        llm_model=_optional(env, "LLM_MODEL"),
        llm_timeout_seconds=_float(env, "LLM_TIMEOUT_SECONDS", 60.0),
        llm_temperature=_float(env, "LLM_TEMPERATURE", 0.0),
        qlib_provider_uri=env.get("QLIB_PROVIDER_URI", "~/.qlib/qlib_data/cn_data"),
        qlib_region=env.get("QLIB_REGION", "cn"),
        qlib_benchmark=env.get("QLIB_BENCHMARK", "SH000300"),
        qlib_deal_price=env.get("QLIB_DEAL_PRICE", "close"),
        qlib_limit_threshold=_float(env, "QLIB_LIMIT_THRESHOLD", 0.095),
        qlib_open_cost=_float(env, "QLIB_OPEN_COST", 0.0005),
        qlib_close_cost=_float(env, "QLIB_CLOSE_COST", 0.0015),
        qlib_min_cost=_float(env, "QLIB_MIN_COST", 5.0),
        qlib_account=_float(env, "QLIB_ACCOUNT", 100000000.0),
    )


def _read_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = _strip_quotes(value.strip())
    return values


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _optional(env: dict[str, str], key: str) -> str | None:
    value = env.get(key)
    return value if value != "" else None


def _float(env: dict[str, str], key: str, default: float) -> float:
    value = env.get(key)
    if value in (None, ""):
        return default
    return float(value)
