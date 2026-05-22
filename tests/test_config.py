from pathlib import Path
import tomllib

from src.config import load_settings


def test_load_settings_uses_documented_qlib_defaults_when_env_missing(tmp_path):
    settings = load_settings(tmp_path / ".env")

    assert settings.qlib_provider_uri == "~/.qlib/qlib_data/cn_data"
    assert settings.qlib_region == "cn"
    assert settings.qlib_benchmark == "SH000300"
    assert settings.qlib_deal_price == "close"
    assert settings.qlib_limit_threshold == 0.095
    assert settings.qlib_open_cost == 0.0005
    assert settings.qlib_close_cost == 0.0015
    assert settings.qlib_min_cost == 5.0
    assert settings.qlib_account == 100000000.0


def test_load_settings_reads_dotenv_values_without_printing_secrets(tmp_path, capsys):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "LLM_API_BASE=https://api.example.test/v1",
                "LLM_API_KEY=secret-value",
                "LLM_MODEL=test-model",
                "LLM_TIMEOUT_SECONDS=12.5",
                "LLM_TEMPERATURE=0.2",
                "QLIB_PROVIDER_URI=/data/qlib",
                "QLIB_REGION=cn",
                "QLIB_BENCHMARK=SH000905",
                "QLIB_DEAL_PRICE=open",
                "QLIB_LIMIT_THRESHOLD=0.1",
                "QLIB_OPEN_COST=0.001",
                "QLIB_CLOSE_COST=0.002",
                "QLIB_MIN_COST=3",
                "QLIB_ACCOUNT=5000000",
            ]
        ),
        encoding="utf-8",
    )

    settings = load_settings(env_path)
    captured = capsys.readouterr()

    assert settings.llm_api_base == "https://api.example.test/v1"
    assert settings.llm_api_key == "secret-value"
    assert settings.llm_model == "test-model"
    assert settings.llm_timeout_seconds == 12.5
    assert settings.llm_temperature == 0.2
    assert settings.qlib_provider_uri == "/data/qlib"
    assert settings.qlib_benchmark == "SH000905"
    assert settings.qlib_deal_price == "open"
    assert settings.qlib_limit_threshold == 0.1
    assert settings.qlib_open_cost == 0.001
    assert settings.qlib_close_cost == 0.002
    assert settings.qlib_min_cost == 3.0
    assert settings.qlib_account == 5000000.0
    assert "secret-value" not in captured.out
    assert "secret-value" not in captured.err


def test_load_settings_allows_process_env_to_override_dotenv(tmp_path, monkeypatch):
    env_path = Path(tmp_path / ".env")
    env_path.write_text("QLIB_BENCHMARK=SH000300\n", encoding="utf-8")
    monkeypatch.setenv("QLIB_BENCHMARK", "SH000905")

    settings = load_settings(env_path)

    assert settings.qlib_benchmark == "SH000905"


def test_pyproject_declares_active_qlib_dependency_baseline():
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    dependencies = pyproject["project"]["dependencies"]

    assert "pandas>=1.5,<2" in dependencies
    assert "pyqlib>=0.9.7,<0.10" in dependencies
