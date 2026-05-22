from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
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
_PRESET_POOL_ALIASES: dict[str, set[str]] = {
    "CSI300": {"沪深300", "沪深 300", "CSI300", "csi300", "HS300"},
    "CSI500": {"中证500", "中证 500", "CSI500", "csi500"},
    "CSI1000": {"中证1000", "中证 1000", "CSI1000", "csi1000"},
    "SSE50": {"上证50", "上证 50", "SSE50", "sse50"},
}


class LLMOutputContractError(ValidationError):
    """Raised when the LLM output violates the parser-owned output contract."""


class LLMClientError(RuntimeError):
    """Raised when the LLM API call fails before returning usable content."""


class LLMResponseFormatUnsupportedError(LLMClientError):
    """Raised when the provider rejects json_schema response_format."""


class LLMParseDraft(BaseModel):
    """Strict LLM-facing parser output."""

    model_config = ConfigDict(extra="forbid")

    dsl: dict[str, Any]
    strategy_kind: Literal["timeseries", "cross_sectional", "unsupported"]
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    human_summary: str = ""


@dataclass(frozen=True)
class OpenAICompatibleLLMClient:
    settings: Settings

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        json_schema: dict[str, Any] | None = None,
    ) -> str:
        if not (
            self.settings.llm_api_base
            and self.settings.llm_api_key
            and self.settings.llm_model
        ):
            raise LLMClientError("LLM API settings are incomplete")

        endpoint = _chat_completion_endpoint(self.settings.llm_api_base)
        payload = {
            "model": self.settings.llm_model,
            "temperature": self.settings.llm_temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if json_schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "nltrader_parse_draft",
                    "strict": True,
                    "schema": json_schema,
                },
            }
        else:
            payload["response_format"] = {"type": "json_object"}
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
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            if json_schema is not None and _looks_like_schema_unsupported(
                exc.code, error_body
            ):
                raise LLMResponseFormatUnsupportedError(error_body) from exc
            raise LLMClientError(
                f"LLM API request failed: HTTP {exc.code}: {error_body}"
            ) from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise LLMClientError(f"LLM API request failed: {exc}") from exc

        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMClientError(
                "LLM API response did not include message content"
            ) from exc

        if not isinstance(content, str):
            raise LLMClientError("LLM API response message content must be a string")
        return content


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

        previous_raw: str | None = None
        last_contract_error: LLMOutputContractError | None = None

        for attempt in range(2):
            repaired = attempt == 1
            user_prompt = (
                _build_user_prompt(normalized)
                if not repaired
                else _build_repair_prompt(
                    normalized,
                    previous_raw=previous_raw or "",
                    validation_error=str(last_contract_error),
                )
            )

            try:
                raw = self._complete_parse_json(_build_system_prompt(), user_prompt)
            except LLMClientError as exc:
                if not fallback:
                    raise
                fallback_result = _fallback_parse(normalized)
                fallback_result.warnings.append(f"Used limited fallback parser: {exc}")
                return fallback_result

            previous_raw = raw
            try:
                draft = _parse_draft_with_contract(raw, source_text=normalized)
                return _draft_to_parse_result(draft, repaired=repaired)
            except LLMOutputContractError as exc:
                last_contract_error = exc

        raise LLMOutputContractError(
            f"LLM output failed parser contract after repair: {last_contract_error}"
        )

    def _complete_parse_json(self, system_prompt: str, user_prompt: str) -> str:
        try:
            return self.llm_client.complete_json(
                system_prompt,
                user_prompt,
                json_schema=llm_parse_draft_json_schema(),
            )
        except LLMResponseFormatUnsupportedError:
            return self.llm_client.complete_json(
                system_prompt,
                user_prompt,
                json_schema=None,
            )


def parse_strategy(text: str, *, fallback: bool = True) -> ParseResult:
    return StrategyParser().parse(text, fallback=fallback)


def llm_parse_draft_json_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "dsl": {
                "type": "object",
                "description": "Controlled NLTrader DSL object. Empty object when unsupported.",
                "additionalProperties": True,
            },
            "strategy_kind": {
                "type": "string",
                "enum": ["timeseries", "cross_sectional", "unsupported"],
            },
            "assumptions": {
                "type": "array",
                "items": {"type": "string"},
            },
            "warnings": {
                "type": "array",
                "items": {"type": "string"},
            },
            "human_summary": {"type": "string"},
        },
        "required": [
            "dsl",
            "strategy_kind",
            "assumptions",
            "warnings",
            "human_summary",
        ],
        "additionalProperties": False,
    }


def parse_llm_draft_from_text(raw_text: str) -> LLMParseDraft:
    try:
        data = json.loads(_strip_code_fences(raw_text))
    except json.JSONDecodeError as exc:
        raise LLMOutputContractError(f"LLM output is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise LLMOutputContractError("LLM output must be a JSON object")

    try:
        return LLMParseDraft.model_validate(data)
    except PydanticValidationError as exc:
        raise LLMOutputContractError(f"invalid LLMParseDraft schema: {exc}") from exc


def _parse_draft_with_contract(raw: str, *, source_text: str) -> LLMParseDraft:
    draft = parse_llm_draft_from_text(raw)

    if draft.strategy_kind == "unsupported" or not draft.dsl:
        if draft.dsl:
            raise LLMOutputContractError("unsupported draft must use empty dsl")
        return draft

    dsl = dict(draft.dsl)
    try:
        _reject_unknown_dsl_fields(dsl)
        _reject_unsafe_dsl_values(dsl)
        dsl = validate_dsl(dsl)
        _assert_grounded_in_input(dsl, source_text)
    except ValidationError as exc:
        raise LLMOutputContractError(str(exc)) from exc
    except ValueError as exc:
        raise LLMOutputContractError(str(exc)) from exc

    if draft.strategy_kind != dsl["strategy_kind"]:
        raise LLMOutputContractError(
            f"strategy_kind mismatch: draft={draft.strategy_kind!r}, dsl={dsl['strategy_kind']!r}"
        )

    return draft.model_copy(update={"dsl": dsl})


def _draft_to_parse_result(
    draft: LLMParseDraft,
    *,
    repaired: bool = False,
) -> ParseResult:
    return ParseResult(
        dsl=dict(draft.dsl),
        strategy_kind=draft.strategy_kind,
        assumptions=list(draft.assumptions),
        warnings=list(draft.warnings),
        human_summary=draft.human_summary,
        parse_confidence=_compute_parse_confidence(draft, repaired=repaired),
    )


def _compute_parse_confidence(
    draft: LLMParseDraft,
    *,
    repaired: bool = False,
) -> float:
    if draft.strategy_kind == "unsupported" or not draft.dsl:
        return 0.1

    score = 0.9
    if repaired:
        score -= 0.1
    if draft.assumptions:
        score -= 0.15
    if draft.warnings:
        score -= 0.2
    return max(0.4, min(score, 0.9))


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
你的任务是把中文策略翻译为 NLTrader 受控 DSL 候选对象 LLMParseDraft。
只支持 A 股日频 CN_A/D、long-only、timeseries 和 cross_sectional。
支持指标: {", ".join(sorted(SUPPORTED_INDICATORS))}。
横截面打分因子: {", ".join(sorted(SUPPORTED_SCORE_FACTORS))}。
支持操作符: {", ".join(sorted(SUPPORTED_OPERATORS))}。
支持调仓频率: {", ".join(sorted(SUPPORTED_REBALANCE_FREQUENCIES))}。
股票代码必须输出 Qlib 风格，如 SH600036、SZ000001。
输出 JSON 顶层字段只能是: dsl, strategy_kind, assumptions, warnings, human_summary。
不要输出 parse_confidence；parse_confidence 由后端 parser 计算。
不要输出 Python 代码、Qlib YAML、Qlib 表达式、markdown 或 JSON 外文本。

重要字段规则：
- risk.stop_loss 必须是数字比例，例如亏损8%输出 0.08。
- selection.score 只能使用 factor 字段和数组 params，例如 {{"factor":"RETURN_N","params":[20]}}。
- 禁止 selection.score.indicator。
- 禁止 params 对象，例如 {{"n":20}}。
表达式 value 只能是数字或 bool，禁止字符串表达式。
- 不要编造用户没有明确给出的股票代码、股票池或指数池。

缺少必要信息时返回 unsupported + 空 DSL + warnings。
超出支持范围或缺少必要 universe 时，返回 dsl={{}}, strategy_kind="unsupported"，并在 warnings 说明原因。
不支持分钟级、公告/财报事件驱动、做空、杠杆。
输出必须是 LLMParseDraft JSON 对象。"""


def _build_user_prompt(text: str) -> str:
    return f"""把下面中文策略翻译为 LLMParseDraft JSON。

LLMParseDraft 顶层结构：
{{
  "dsl": {{}},
  "strategy_kind": "timeseries" | "cross_sectional" | "unsupported",
  "assumptions": [],
  "warnings": [],
  "human_summary": ""
}}

DSL timeseries 结构包含 strategy_kind, market, frequency, universe, rebalance, signal(entry_rules/exit_rules), 可选 risk(stop_loss)。
DSL cross_sectional 结构包含 strategy_kind, market, frequency, universe, rebalance, selection(filters/score/rank_order/top_n 或 bottom_n), construction(weighting="equal_weight")。
规则表达式只能用 lhs/op/rhs；表达式只能用 indicator/params 或 value。

关键约束：
- 不要输出 parse_confidence。
- risk.stop_loss 是数字比例：亏损8% => 0.08。
- 横截面 score 必须写为 {{"factor":"RETURN_N","params":[20]}}，不要写 indicator 或 {{"n":20}}。
- 如果用户没有给出股票池、股票列表或明确指数池，不要编造 universe；返回 unsupported 并写 warnings。

参考示例：
{_build_few_shot_examples()}

用户策略: {text}"""


def _build_repair_prompt(
    text: str,
    *,
    previous_raw: str,
    validation_error: str,
) -> str:
    return f"""你上一次输出的 JSON 没有通过 NLTrader parser 契约校验。
请只修复 JSON，不要重新解释用户策略，不要改变用户策略含义，不要新增字段，不要输出 markdown，不要输出 JSON 外文本。

原始用户策略：
{text}

上一次输出：
{previous_raw}

校验错误：
{validation_error}

必须满足：
- 顶层字段只能是 dsl, strategy_kind, assumptions, warnings, human_summary。
- 不要输出 parse_confidence。
- risk.stop_loss 必须是数字比例，例如亏损8% => 0.08。
- selection.score 必须是 {{"factor":"RETURN_N","params":[20]}}，不能使用 indicator。
- params 必须是数组，不能是 {{"n":20}}。
- 表达式 value 只能是数字或 bool，不能是字符串表达式。
- 股票代码和股票池必须来自原始用户策略；缺少股票池/股票代码时不要编造。
- 如果无法在契约内表达，请返回 dsl={{}}, strategy_kind="unsupported" 并写 warnings。
"""


def _build_few_shot_examples() -> str:
    return """示例 1
输入：针对招商银行600036，5日均线上穿20日均线买入，亏损8%卖出。
输出：
{
  "dsl": {
    "strategy_kind": "timeseries",
    "market": "CN_A",
    "frequency": "D",
    "universe": {"type": "single_symbol", "symbols": ["SH600036"]},
    "rebalance": {"freq": "daily"},
    "signal": {
      "entry_rules": [
        {
          "lhs": {"indicator": "SMA", "params": [5]},
          "op": "cross_above",
          "rhs": {"indicator": "SMA", "params": [20]}
        }
      ],
      "exit_rules": []
    },
    "risk": {"stop_loss": 0.08}
  },
  "strategy_kind": "timeseries",
  "assumptions": [],
  "warnings": [],
  "human_summary": "单股均线交叉买入，亏损8%止损。"
}

示例 2
输入：每月调仓，在股票池600036、000001、600519中选择过去20日涨幅最高的2只股票等权持有。
输出：
{
  "dsl": {
    "strategy_kind": "cross_sectional",
    "market": "CN_A",
    "frequency": "D",
    "universe": {"type": "symbol_list", "symbols": ["SH600036", "SZ000001", "SH600519"]},
    "rebalance": {"freq": "monthly"},
    "selection": {
      "filters": [],
      "score": {"factor": "RETURN_N", "params": [20]},
      "rank_order": "desc",
      "top_n": 2
    },
    "construction": {"weighting": "equal_weight"}
  },
  "strategy_kind": "cross_sectional",
  "assumptions": [],
  "warnings": [],
  "human_summary": "股票池内按20日收益率月度选前2只等权持有。"
}

示例 3
输入：每月选过去20日涨幅最高的10只股票等权持有。
输出：
{
  "dsl": {},
  "strategy_kind": "unsupported",
  "assumptions": [],
  "warnings": ["缺少明确股票池、股票列表或指数池，无法执行横截面选股。"],
  "human_summary": "横截面选股策略缺少 universe。"
}
禁止：
{
  "universe": {"type": "preset_pool", "pool_name": "CSI300"}
}"""


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


def _assert_grounded_in_input(dsl: dict[str, Any], source_text: str) -> None:
    universe = dsl.get("universe")
    if not isinstance(universe, dict):
        return

    source_symbols = set(_extract_symbols(source_text))
    dsl_symbols = set(universe.get("symbols", []))
    invented_symbols = dsl_symbols - source_symbols
    if invented_symbols:
        raise LLMOutputContractError(
            f"LLM invented symbols not present in user input: {sorted(invented_symbols)}"
        )

    universe_type = universe.get("type")
    if universe_type == "uploaded_pool":
        raise LLMOutputContractError(
            "uploaded_pool requires external uploaded universe context"
        )

    if universe_type == "preset_pool":
        mentioned_pools = _extract_preset_pool_mentions(source_text)
        pool_values = [universe.get("pool_name"), universe.get("qlib_market")]
        if not any(
            _pool_name_matches_mention(value, mentioned_pools) for value in pool_values
        ):
            raise LLMOutputContractError(
                "LLM invented preset_pool not explicitly mentioned in user input"
            )


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
    symbol = _extract_symbol(text)
    if not symbol:
        return _unsupported_result("有限 fallback 解析器无法在输入中找到股票代码。")
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


def _extract_preset_pool_mentions(text: str) -> set[str]:
    mentions: set[str] = set()
    lowered = text.lower()
    compact_lowered = re.sub(r"\s+", "", lowered)

    for canonical, aliases in _PRESET_POOL_ALIASES.items():
        for alias in aliases:
            alias_lower = alias.lower()
            alias_compact = re.sub(r"\s+", "", alias_lower)
            if alias_lower in lowered or alias_compact in compact_lowered:
                mentions.add(canonical)
                break
    return mentions


def _pool_name_matches_mention(pool_value: object, mentioned_pools: set[str]) -> bool:
    if not isinstance(pool_value, str) or not pool_value.strip():
        return False
    normalized = re.sub(r"[^a-z0-9]", "", pool_value.lower())
    for canonical in mentioned_pools:
        if normalized == re.sub(r"[^a-z0-9]", "", canonical.lower()):
            return True
    return False


def _chat_completion_endpoint(api_base: str) -> str:
    base = api_base.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    if base.endswith("/v1"):
        return f"{base}/chat/completions"
    return f"{base}/v1/chat/completions"


def _looks_like_schema_unsupported(status_code: int, error_body: str) -> bool:
    if status_code not in {400, 422}:
        return False
    lowered = error_body.lower()
    return "response_format" in lowered and (
        "json_schema" in lowered or "strict" in lowered or "unsupported" in lowered
    )
