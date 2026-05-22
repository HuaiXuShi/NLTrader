from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError as PydanticValidationError

from src.config import Settings, load_settings
from src.dsl import (
    SUPPORTED_INDICATORS,
    SUPPORTED_OPERATORS,
    SUPPORTED_REBALANCE_FREQUENCIES,
    SUPPORTED_SCORE_FACTORS,
    ValidationError,
    validate_dsl,
)
from src.models import ParseResult
from src.symbols import normalize_symbol


PROMPT_VERSION = "p1"
DSL_VERSION = "v1"
_PARSE_RESULT_FIELDS = {
    "dsl",
    "strategy_kind",
    "assumptions",
    "warnings",
    "human_summary",
    "parse_confidence",
}
_DSL_TOP_LEVEL_FIELDS = {
    "strategy_kind",
    "market",
    "frequency",
    "universe",
    "rebalance",
    "signal",
    "selection",
    "construction",
    "risk",
}
_UNIVERSE_FIELDS = {"type", "symbols", "pool_name", "qlib_market"}
_REBALANCE_FIELDS = {"freq"}
_SIGNAL_FIELDS = {"entry_rules", "exit_rules"}
_RULE_FIELDS = {"lhs", "op", "rhs"}
_EXPRESSION_FIELDS = {"indicator", "params", "value"}
_SELECTION_FIELDS = {"filters", "score", "rank_order", "top_n", "bottom_n"}
_SCORE_FIELDS = {"factor", "params"}
_CONSTRUCTION_FIELDS = {"weighting"}
_RISK_FIELDS = {"stop_loss"}


@dataclass(frozen=True)
class OpenAICompatibleLLMClient:
    settings: Settings

    def complete_json(self, system_prompt: str, user_prompt: str) -> str:
        if not (
            self.settings.llm_api_base
            and self.settings.llm_api_key
            and self.settings.llm_model
        ):
            raise RuntimeError("LLM API settings are incomplete")

        endpoint = _chat_completion_endpoint(self.settings.llm_api_base)
        payload = {
            "model": self.settings.llm_model,
            "temperature": self.settings.llm_temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
        }
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            endpoint,
            data=data,
            headers={
                "Authorization": f"Bearer {self.settings.llm_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request, timeout=self.settings.llm_timeout_seconds
            ) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"LLM API request failed: {exc}") from exc

        try:
            return body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("LLM API response did not include message content") from exc


class StrategyParser:
    def __init__(
        self,
        settings: Settings | None = None,
        llm_client: OpenAICompatibleLLMClient | None = None,
    ) -> None:
        self.settings = settings or load_settings()
        self.llm_client = llm_client or OpenAICompatibleLLMClient(self.settings)

    def parse(self, text: str, *, fallback: bool = True) -> ParseResult:
        normalized = _normalize_input(text)
        unsupported = _detect_unsupported(normalized)
        if unsupported:
            return _unsupported_result(unsupported)

        try:
            raw = self.llm_client.complete_json(
                _build_system_prompt(), _build_user_prompt(normalized)
            )
            return parse_result_from_text(raw)
        except Exception as exc:
            if not fallback:
                raise
            fallback_result = _fallback_parse(normalized)
            fallback_result.warnings.append(f"Used limited fallback parser: {exc}")
            return fallback_result


def parse_strategy(text: str, *, fallback: bool = True) -> ParseResult:
    return StrategyParser().parse(text, fallback=fallback)


def parse_result_from_text(raw_text: str) -> ParseResult:
    data = json.loads(_strip_code_fences(raw_text))
    if not isinstance(data, dict):
        raise ValueError("LLM output must be a JSON object")

    if "dsl" not in data and "strategy_kind" in data:
        data = {
            "dsl": data,
            "strategy_kind": data.get("strategy_kind"),
            "assumptions": [
                "Model returned DSL without ParseResult wrapper; wrapper was repaired."
            ],
            "warnings": ["Light repair applied: unwrapped bare DSL JSON."],
            "human_summary": "",
            "parse_confidence": 0.4,
        }

    repaired = _normalize_known_aliases(data)
    _reject_unknown_parse_result_fields(repaired)

    try:
        result = ParseResult.model_validate(repaired)
    except PydanticValidationError as exc:
        raise ValueError(f"invalid ParseResult schema: {exc}") from exc

    if result.dsl:
        _reject_unknown_dsl_fields(result.dsl)
        _reject_unsafe_dsl_values(result.dsl)
        result.dsl = validate_dsl(result.dsl)
        if result.strategy_kind != result.dsl["strategy_kind"]:
            result.strategy_kind = result.dsl["strategy_kind"]
    return result


def _build_system_prompt() -> str:
    return f"""你是一个量化策略解析器，prompt_version={PROMPT_VERSION}, dsl_version={DSL_VERSION}。
只支持 A 股日频 CN_A/D，long-only，只支持 timeseries 和 cross_sectional。
支持指标: {", ".join(sorted(SUPPORTED_INDICATORS))}。
横截面打分因子: {", ".join(sorted(SUPPORTED_SCORE_FACTORS))}。
支持操作符: {", ".join(sorted(SUPPORTED_OPERATORS))}。
支持调仓频率: {", ".join(sorted(SUPPORTED_REBALANCE_FREQUENCIES))}。
股票代码必须输出 Qlib 风格，如 SH600036、SZ000001。
禁止输出 Python 代码、Qlib YAML、Qlib 表达式、markdown、未知字段或 JSON 外文本。
selection.score 只能使用 factor 字段和数组 params，例如 {{"factor":"RETURN_N","params":[20]}}；禁止 indicator 或 params 对象。
表达式 value 只能是数字或 bool，禁止字符串表达式。
不支持分钟级、公告/财报事件驱动、做空、杠杆；超出范围时返回 dsl={{}}、strategy_kind="unsupported" 并写 warnings。
必须输出 JSON 对象，字段只能是 dsl, strategy_kind, assumptions, warnings, human_summary, parse_confidence。"""


def _build_user_prompt(text: str) -> str:
    return f"""把下面中文策略翻译为受控 JSON ParseResult。
DSL timeseries 结构包含 strategy_kind, market, frequency, universe, rebalance, signal(entry_rules/exit_rules), 可选 risk(stop_loss)。
DSL cross_sectional 结构包含 strategy_kind, market, frequency, universe, rebalance, selection(filters/score/rank_order/top_n 或 bottom_n), construction(weighting="equal_weight")。
规则表达式只能用 lhs/op/rhs；表达式只能用 indicator/params 或 value。
横截面 score 必须写为 {{"factor":"RETURN_N","params":[20]}}，不要写 indicator 或 {{"n":20}}。
用户策略: {text}"""


def _strip_code_fences(text: str) -> str:
    value = text.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", value, flags=re.IGNORECASE | re.S)
    return match.group(1).strip() if match else value


def _normalize_known_aliases(data: dict[str, Any]) -> dict[str, Any]:
    repaired = dict(data)
    if "strategy_kind" in repaired and isinstance(repaired["strategy_kind"], str):
        repaired["strategy_kind"] = repaired["strategy_kind"].strip().lower()
    if isinstance(repaired.get("dsl"), dict):
        repaired["dsl"] = _normalize_dsl_aliases(repaired["dsl"])
    return repaired


def _normalize_dsl_aliases(dsl: dict[str, Any]) -> dict[str, Any]:
    repaired = dict(dsl)
    for field in ("strategy_kind", "market", "frequency"):
        if isinstance(repaired.get(field), str):
            repaired[field] = repaired[field].strip()
    if isinstance(repaired.get("strategy_kind"), str):
        repaired["strategy_kind"] = repaired["strategy_kind"].lower()
    if isinstance(repaired.get("market"), str):
        repaired["market"] = repaired["market"].upper()
    if isinstance(repaired.get("frequency"), str):
        frequency = repaired["frequency"].upper()
        repaired["frequency"] = "D" if frequency in {"DAILY", "DAY"} else frequency
    if isinstance(repaired.get("universe"), list):
        universe_type = "single_symbol" if len(repaired["universe"]) == 1 else "symbol_list"
        repaired["universe"] = {
            "type": universe_type,
            "symbols": repaired["universe"],
        }
    if isinstance(repaired.get("rebalance"), str):
        repaired["rebalance"] = {"freq": repaired["rebalance"].strip().lower()}
    if isinstance(repaired.get("rebalance"), dict):
        rebalance = dict(repaired["rebalance"])
        if isinstance(rebalance.get("freq"), str):
            rebalance["freq"] = rebalance["freq"].strip().lower()
        repaired["rebalance"] = rebalance
    return repaired


def _reject_unknown_parse_result_fields(data: dict[str, Any]) -> None:
    unknown = set(data) - _PARSE_RESULT_FIELDS
    if unknown:
        raise ValueError(f"unknown ParseResult fields: {sorted(unknown)}")


def _reject_unknown_dsl_fields(dsl: dict[str, Any]) -> None:
    _reject_unknown_fields(dsl, _DSL_TOP_LEVEL_FIELDS, "dsl")
    if isinstance(dsl.get("universe"), dict):
        _reject_unknown_fields(dsl["universe"], _UNIVERSE_FIELDS, "dsl.universe")
    if isinstance(dsl.get("rebalance"), dict):
        _reject_unknown_fields(dsl["rebalance"], _REBALANCE_FIELDS, "dsl.rebalance")
    if isinstance(dsl.get("signal"), dict):
        _reject_unknown_fields(dsl["signal"], _SIGNAL_FIELDS, "dsl.signal")
        _reject_rule_list(dsl["signal"].get("entry_rules", []), "dsl.signal.entry_rules")
        _reject_rule_list(dsl["signal"].get("exit_rules", []), "dsl.signal.exit_rules")
    if isinstance(dsl.get("selection"), dict):
        selection = dsl["selection"]
        _reject_unknown_fields(selection, _SELECTION_FIELDS, "dsl.selection")
        _reject_rule_list(selection.get("filters", []), "dsl.selection.filters")
        if isinstance(selection.get("score"), dict):
            _reject_unknown_fields(selection["score"], _SCORE_FIELDS, "dsl.selection.score")
    if isinstance(dsl.get("construction"), dict):
        _reject_unknown_fields(
            dsl["construction"], _CONSTRUCTION_FIELDS, "dsl.construction"
        )
    if isinstance(dsl.get("risk"), dict):
        _reject_unknown_fields(dsl["risk"], _RISK_FIELDS, "dsl.risk")


def _reject_rule_list(rules: Any, path: str) -> None:
    if not isinstance(rules, list):
        return
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            continue
        _reject_unknown_fields(rule, _RULE_FIELDS, f"{path}[{index}]")
        for side in ("lhs", "rhs"):
            if isinstance(rule.get(side), dict):
                _reject_unknown_fields(
                    rule[side], _EXPRESSION_FIELDS, f"{path}[{index}].{side}"
                )


def _reject_unknown_fields(data: dict[str, Any], allowed: set[str], path: str) -> None:
    unknown = set(data) - allowed
    if unknown:
        raise ValueError(f"unknown {path} fields: {sorted(unknown)}")


def _reject_unsafe_dsl_values(dsl: dict[str, Any]) -> None:
    if isinstance(dsl.get("signal"), dict):
        _reject_unsafe_rule_values(
            dsl["signal"].get("entry_rules", []), "dsl.signal.entry_rules"
        )
        _reject_unsafe_rule_values(
            dsl["signal"].get("exit_rules", []), "dsl.signal.exit_rules"
        )
    if isinstance(dsl.get("selection"), dict):
        selection = dsl["selection"]
        _reject_unsafe_rule_values(
            selection.get("filters", []), "dsl.selection.filters"
        )
        if isinstance(selection.get("score"), dict):
            score = selection["score"]
            if "params" in score and not isinstance(score["params"], list):
                raise ValueError("dsl.selection.score.params must be a list")


def _reject_unsafe_rule_values(rules: Any, path: str) -> None:
    if not isinstance(rules, list):
        return
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            continue
        for side in ("lhs", "rhs"):
            expression = rule.get(side)
            if not isinstance(expression, dict) or "value" not in expression:
                continue
            value = expression["value"]
            if not isinstance(value, (int, float, bool)):
                raise ValueError(
                    f"{path}[{index}].{side} expression value must be numeric or bool"
                )


def _normalize_input(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _detect_unsupported(text: str) -> str | None:
    lowered = text.lower()
    checks = [
        ("分钟", "当前系统不支持分钟级或盘中策略，只支持 A 股日频策略。"),
        ("minute", "当前系统不支持分钟级或盘中策略，只支持 A 股日频策略。"),
        ("公告", "当前系统不支持公告/事件驱动策略。"),
        ("财报", "当前系统不支持公告/事件驱动策略。"),
        ("event", "当前系统不支持公告/事件驱动策略。"),
        ("做空", "当前系统不支持做空策略，只支持 long-only。"),
        ("short", "当前系统不支持做空策略，只支持 long-only。"),
        ("杠杆", "当前系统不支持杠杆策略。"),
        ("leverage", "当前系统不支持杠杆策略。"),
    ]
    for token, warning in checks:
        if token in lowered:
            return warning
    return None


def _unsupported_result(warning: str) -> ParseResult:
    return ParseResult(
        dsl={},
        strategy_kind="unsupported",
        assumptions=[],
        warnings=[warning],
        human_summary="请求超出当前解析器支持范围。",
        parse_confidence=0.1,
    )


def _fallback_parse(text: str) -> ParseResult:
    if _looks_cross_sectional_momentum(text) and _extract_symbols(text):
        return _fallback_cross_sectional_momentum(text)
    if _looks_moving_average(text):
        return _fallback_moving_average(text)
    return _unsupported_result("有限 fallback 解析器未识别出受支持的策略模板。")


def _fallback_moving_average(text: str) -> ParseResult:
    symbol = _extract_symbol(text) or "SH600036"
    periods = [int(value) for value in re.findall(r"(\d+)\s*日均线", text)]
    fast = periods[0] if periods else 5
    slow = periods[1] if len(periods) > 1 else 20
    exit_period = periods[2] if len(periods) > 2 else 10
    dsl = {
        "strategy_kind": "timeseries",
        "market": "CN_A",
        "frequency": "D",
        "universe": {"type": "single_symbol", "symbols": [symbol]},
        "rebalance": {"freq": "daily"},
        "signal": {
            "entry_rules": [
                {
                    "lhs": {"indicator": "SMA", "params": [fast]},
                    "op": "cross_above",
                    "rhs": {"indicator": "SMA", "params": [slow]},
                }
            ],
            "exit_rules": [
                {
                    "lhs": {"indicator": "CLOSE"},
                    "op": "<",
                    "rhs": {"indicator": "SMA", "params": [exit_period]},
                }
            ],
        },
    }
    return ParseResult(
        dsl=validate_dsl(dsl),
        strategy_kind="timeseries",
        assumptions=[],
        warnings=[],
        human_summary="有限 fallback 解析为单股均线时序策略。",
        parse_confidence=0.45,
    )


def _fallback_cross_sectional_momentum(text: str) -> ParseResult:
    symbols = _extract_symbols(text)
    if not symbols:
        raise ValueError("fallback cross-sectional parser requires explicit symbols")
    top_n_match = re.search(r"(?:前|top\s*)(\d+)|(\d+)\s*只", text, flags=re.I)
    return_n_match = re.search(r"过去\s*(\d+)\s*日", text)
    top_n = int(next(value for value in top_n_match.groups() if value)) if top_n_match else 10
    return_n = int(return_n_match.group(1)) if return_n_match else 20
    dsl = {
        "strategy_kind": "cross_sectional",
        "market": "CN_A",
        "frequency": "D",
        "universe": {"type": "symbol_list", "symbols": symbols},
        "rebalance": {"freq": "monthly" if "月" in text else "daily"},
        "selection": {
            "filters": [],
            "score": {"factor": "RETURN_N", "params": [return_n]},
            "rank_order": "desc",
            "top_n": top_n,
        },
        "construction": {"weighting": "equal_weight"},
    }
    return ParseResult(
        dsl=validate_dsl(dsl),
        strategy_kind="cross_sectional",
        assumptions=[],
        warnings=[],
        human_summary="有限 fallback 解析为横截面动量等权策略。",
        parse_confidence=0.45,
    )


def _looks_cross_sectional_momentum(text: str) -> bool:
    return ("股票池" in text or "等权" in text or "top" in text.lower()) and (
        "涨幅" in text or "动量" in text or "return" in text.lower()
    )


def _looks_moving_average(text: str) -> bool:
    lowered = text.lower()
    return (
        "均线" in text
        or re.search(r"\b(?:sma|ma)\s*\d+\b", lowered) is not None
        or re.search(r"\d+\s*(?:日|day)?\s*(?:sma|ma)\b", lowered) is not None
    )


def _extract_symbol(text: str) -> str | None:
    symbols = _extract_symbols(text)
    return symbols[0] if symbols else None


def _extract_symbols(text: str) -> list[str]:
    raw_symbols = re.findall(r"(?<!\d)(?:SH|SZ)?\d{6}(?:\.(?:SH|SZ))?(?!\d)", text, re.I)
    normalized: list[str] = []
    for raw_symbol in raw_symbols:
        try:
            symbol = normalize_symbol(raw_symbol)
        except ValueError:
            continue
        if symbol not in normalized:
            normalized.append(symbol)
    return normalized


def _chat_completion_endpoint(api_base: str) -> str:
    base = api_base.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    if base.endswith("/v1"):
        return f"{base}/chat/completions"
    return f"{base}/v1/chat/completions"
