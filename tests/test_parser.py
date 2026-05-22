import json

import pytest

from src.compiler import compile_strategy
from src.config import Settings
from src.dsl import validate_dsl
from src.parser import (
    LLMClientError,
    LLMParseDraft,
    LLMOutputContractError,
    LLMResponseFormatUnsupportedError,
    StrategyParser,
    _build_system_prompt,
    _build_user_prompt,
    _build_repair_prompt,
    _draft_to_parse_result,
    _parse_draft_with_contract,
    llm_parse_draft_json_schema,
    parse_llm_draft_from_text,
    parse_result_from_text,
    parse_strategy,
)


class FakeSchemaAwareLLMClient:
    def __init__(self, responses: list[object]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        json_schema: dict[str, object] | None = None,
    ) -> str:
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "json_schema": json_schema,
            }
        )
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_parse_llm_draft_from_text_parses_code_fence_json_draft():
    raw = """```json
{
  "dsl": {},
  "strategy_kind": "unsupported",
  "assumptions": [],
  "warnings": ["out of scope"],
  "human_summary": "not supported"
}
```"""

    draft = parse_llm_draft_from_text(raw)

    assert isinstance(draft, LLMParseDraft)
    assert draft.strategy_kind == "unsupported"
    assert draft.warnings == ["out of scope"]


def test_parse_llm_draft_from_text_rejects_top_level_parse_confidence():
    raw = {
        "dsl": {},
        "strategy_kind": "unsupported",
        "assumptions": [],
        "warnings": [],
        "human_summary": "",
        "parse_confidence": 0.9,
    }

    with pytest.raises(Exception, match="parse_confidence|schema|unknown"):
        parse_llm_draft_from_text(json.dumps(raw))


def test_draft_to_parse_result_uses_parser_owned_confidence():
    draft = LLMParseDraft(
        dsl={
            "strategy_kind": "timeseries",
            "market": "CN_A",
            "frequency": "D",
            "universe": {"type": "single_symbol", "symbols": ["SH600036"]},
            "rebalance": {"freq": "daily"},
            "signal": {"entry_rules": [], "exit_rules": []},
        },
        strategy_kind="timeseries",
        assumptions=["normalized user wording"],
        warnings=[],
        human_summary="timeseries draft",
    )

    result = _draft_to_parse_result(draft)

    assert result.strategy_kind == "timeseries"
    assert result.parse_confidence == pytest.approx(0.75)


def test_llm_parse_draft_json_schema_requires_all_top_level_fields():
    schema = llm_parse_draft_json_schema()

    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {
        "dsl",
        "strategy_kind",
        "assumptions",
        "warnings",
        "human_summary",
    }


def test_complete_parse_json_falls_back_to_json_object_when_schema_unsupported():
    client = FakeSchemaAwareLLMClient(
        [
            LLMResponseFormatUnsupportedError("json_schema response_format unsupported"),
            '{"dsl":{},"strategy_kind":"unsupported","assumptions":[],"warnings":[],"human_summary":""}',
        ]
    )
    parser = StrategyParser(
        Settings(llm_api_base=None, llm_api_key=None, llm_model=None),
        llm_client=client,
    )

    raw = parser._complete_parse_json("system", "user")

    assert json.loads(raw)["strategy_kind"] == "unsupported"
    assert client.calls[0]["json_schema"] == llm_parse_draft_json_schema()
    assert client.calls[1]["json_schema"] is None
    assert len(client.calls) == 2


def test_parse_retries_with_repair_prompt_after_contract_failure():
    client = FakeSchemaAwareLLMClient(
        [
            json.dumps(
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
                                    "rhs": {"indicator": "SMA", "params": [20]},
                                }
                            ],
                            "exit_rules": [],
                        },
                    },
                    "strategy_kind": "cross_sectional",
                    "assumptions": [],
                    "warnings": [],
                    "human_summary": "bad draft",
                }
            ),
            json.dumps(
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
                                    "rhs": {"indicator": "SMA", "params": [20]},
                                }
                            ],
                            "exit_rules": [],
                        },
                    },
                    "strategy_kind": "timeseries",
                    "assumptions": [],
                    "warnings": [],
                    "human_summary": "fixed draft",
                }
            ),
        ]
    )
    parser = StrategyParser(
        Settings(llm_api_base=None, llm_api_key=None, llm_model=None),
        llm_client=client,
    )

    result = parser.parse("招商银行600036，5日均线上穿20日均线买入。", fallback=True)

    assert result.strategy_kind == "timeseries"
    assert result.parse_confidence == pytest.approx(0.8)
    assert len(client.calls) == 2
    assert "修复" in client.calls[1]["user_prompt"]
    assert "strategy_kind mismatch" in client.calls[1]["user_prompt"]
    assert "bad draft" in client.calls[1]["user_prompt"]


def test_parse_raises_contract_error_after_two_contract_failures_even_with_fallback():
    client = FakeSchemaAwareLLMClient(
        [
            '{"dsl": {}, "strategy_kind": "unsupported", "assumptions": [], "warnings": [], "human_summary": "", "extra": 1}',
            '{"dsl": {"strategy_kind": "unsupported"}, "strategy_kind": "unsupported", "assumptions": [], "warnings": [], "human_summary": ""}',
        ]
    )
    parser = StrategyParser(
        Settings(llm_api_base=None, llm_api_key=None, llm_model=None),
        llm_client=client,
    )

    with pytest.raises(LLMOutputContractError, match="after repair"):
        parser.parse("招商银行600036，5日均线上穿20日均线买入。", fallback=True)

    assert len(client.calls) == 2


def test_parse_only_falls_back_for_llm_client_error_not_contract_error():
    parser = StrategyParser(
        Settings(llm_api_base=None, llm_api_key=None, llm_model=None),
        llm_client=FakeSchemaAwareLLMClient([LLMClientError("network down")]),
    )

    fallback_result = parser.parse("招商银行600036，5日均线上穿20日均线买入。", fallback=True)

    assert fallback_result.strategy_kind == "timeseries"
    assert any("fallback" in warning.lower() for warning in fallback_result.warnings)

    parser = StrategyParser(
        Settings(llm_api_base=None, llm_api_key=None, llm_model=None),
        llm_client=FakeSchemaAwareLLMClient(
            [
                '{"dsl": {}, "strategy_kind": "unsupported", "assumptions": [], "warnings": [], "human_summary": "", "extra": 1}',
                '{"dsl": {}, "strategy_kind": "unsupported", "assumptions": [], "warnings": [], "human_summary": "", "extra": 1}',
            ]
        ),
    )

    with pytest.raises(LLMOutputContractError):
        parser.parse("招商银行600036，5日均线上穿20日均线买入。", fallback=True)


def test_parse_draft_with_contract_rejects_strategy_kind_mismatch():
    raw = json.dumps(
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
                            "rhs": {"indicator": "SMA", "params": [20]},
                        }
                    ],
                    "exit_rules": [],
                },
            },
            "strategy_kind": "cross_sectional",
            "assumptions": [],
            "warnings": [],
            "human_summary": "",
        }
    )

    with pytest.raises(LLMOutputContractError, match="strategy_kind mismatch"):
        _parse_draft_with_contract(raw, source_text="招商银行600036，5日均线上穿20日均线买入。")


def test_parse_draft_with_contract_rejects_unsupported_with_non_empty_dsl():
    raw = json.dumps(
        {
            "dsl": {
                "strategy_kind": "timeseries",
                "market": "CN_A",
                "frequency": "D",
            },
            "strategy_kind": "unsupported",
            "assumptions": [],
            "warnings": ["not supported"],
            "human_summary": "",
        }
    )

    with pytest.raises(LLMOutputContractError, match="unsupported draft must use empty dsl"):
        _parse_draft_with_contract(raw, source_text="不支持的策略")


def test_parse_draft_with_contract_rejects_invented_preset_pool():
    raw = json.dumps(
        {
            "dsl": {
                "strategy_kind": "cross_sectional",
                "market": "CN_A",
                "frequency": "D",
                "universe": {"type": "preset_pool", "pool_name": "CSI300"},
                "rebalance": {"freq": "monthly"},
                "selection": {
                    "filters": [],
                    "score": {"factor": "RETURN_N", "params": [20]},
                    "rank_order": "desc",
                    "top_n": 10,
                },
                "construction": {"weighting": "equal_weight"},
            },
            "strategy_kind": "cross_sectional",
            "assumptions": [],
            "warnings": [],
            "human_summary": "",
        }
    )

    with pytest.raises(LLMOutputContractError, match="invented preset_pool"):
        _parse_draft_with_contract(
            raw,
            source_text="每月选过去20日涨幅最高的10只股票等权持有。",
        )


@pytest.mark.parametrize("mention", ["沪深300", "CSI300"])
def test_parse_draft_with_contract_allows_explicit_preset_pool_mentions(mention):
    raw = json.dumps(
        {
            "dsl": {
                "strategy_kind": "cross_sectional",
                "market": "CN_A",
                "frequency": "D",
                "universe": {"type": "preset_pool", "pool_name": "CSI300"},
                "rebalance": {"freq": "monthly"},
                "selection": {
                    "filters": [],
                    "score": {"factor": "RETURN_N", "params": [20]},
                    "rank_order": "desc",
                    "top_n": 10,
                },
                "construction": {"weighting": "equal_weight"},
            },
            "strategy_kind": "cross_sectional",
            "assumptions": [],
            "warnings": [],
            "human_summary": "",
        }
    )

    draft = _parse_draft_with_contract(
        raw,
        source_text=f"在{mention}里每月选过去20日涨幅最高的10只股票等权持有。",
    )

    assert draft.dsl["universe"]["pool_name"] == "CSI300"


def test_parse_draft_with_contract_rejects_uploaded_pool_without_context():
    raw = json.dumps(
        {
            "dsl": {
                "strategy_kind": "cross_sectional",
                "market": "CN_A",
                "frequency": "D",
                "universe": {"type": "uploaded_pool"},
                "rebalance": {"freq": "monthly"},
                "selection": {
                    "filters": [],
                    "score": {"factor": "RETURN_N", "params": [20]},
                    "rank_order": "desc",
                    "top_n": 10,
                },
                "construction": {"weighting": "equal_weight"},
            },
            "strategy_kind": "cross_sectional",
            "assumptions": [],
            "warnings": [],
            "human_summary": "",
        }
    )

    with pytest.raises(LLMOutputContractError, match="uploaded_pool"):
        _parse_draft_with_contract(
            raw,
            source_text="使用我上传的股票池，每月选过去20日涨幅最高的10只股票等权持有。",
        )


def test_system_and_user_prompts_include_phase_4_contract_constraints():
    system_prompt = _build_system_prompt()
    user_prompt = _build_user_prompt("每月选过去20日涨幅最高的10只股票等权持有。")

    assert "LLMParseDraft" in system_prompt
    assert "不要输出 parse_confidence" in system_prompt
    assert "risk.stop_loss 必须是数字比例" in system_prompt
    assert 'selection.score 只能使用 factor 字段和数组 params' in system_prompt
    assert "不要编造用户没有明确给出的股票代码、股票池或指数池" in system_prompt
    assert '返回 dsl={}, strategy_kind="unsupported"' in system_prompt

    assert "LLMParseDraft 顶层结构" in user_prompt
    assert "risk.stop_loss 是数字比例：亏损8% => 0.08" in user_prompt
    assert 'score 必须写为 {"factor":"RETURN_N","params":[20]}' in user_prompt
    assert "如果用户没有给出股票池、股票列表或明确指数池，不要编造 universe" in user_prompt


def test_build_repair_prompt_targets_json_repair_only():
    prompt = _build_repair_prompt(
        "招商银行600036，5日均线上穿20日均线买入。",
        previous_raw='{"oops":1}',
        validation_error="strategy_kind mismatch",
    )

    assert "只修复 JSON" in prompt
    assert "不要重新解释用户策略" in prompt
    assert "strategy_kind mismatch" in prompt
    assert '{"oops":1}' in prompt


def test_repair_prompt_includes_phase_4_contract_constraints():
    prompt = _build_repair_prompt(
        "每月选过去20日涨幅最高的10只股票等权持有。",
        previous_raw='{"dsl":{"universe":{"type":"preset_pool","pool_name":"CSI300"}}}',
        validation_error="LLM invented preset_pool not explicitly mentioned in user input",
    )

    assert "不要输出 parse_confidence" in prompt
    assert "risk.stop_loss 必须是数字比例" in prompt
    assert 'selection.score 必须是 {"factor":"RETURN_N","params":[20]}' in prompt
    assert "股票代码和股票池必须来自原始用户策略" in prompt
    assert '如果无法在契约内表达，请返回 dsl={}, strategy_kind="unsupported"' in prompt


def test_user_prompt_includes_few_shot_examples_for_fragile_shapes():
    prompt = _build_user_prompt("每月选过去20日涨幅最高的10只股票等权持有。")

    assert "参考示例" in prompt
    assert '"stop_loss": 0.08' in prompt
    assert '"factor": "RETURN_N"' in prompt
    assert '"strategy_kind": "unsupported"' in prompt
    assert '"pool_name": "CSI300"' in prompt


def test_parse_result_from_text_strips_code_fences_and_unwraps_dsl():
    raw = """```json
{
  "strategy_kind": "timeseries",
  "market": "CN_A",
  "frequency": "D",
  "universe": {"type": "single_symbol", "symbols": ["600036.SH"]},
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
  }
}
```"""

    result = parse_result_from_text(raw)

    assert result.strategy_kind == "timeseries"
    assert result.dsl["universe"]["symbols"] == ["SH600036"]
    assert result.parse_confidence == 0.4


def test_parse_result_from_text_rejects_unknown_fields_before_compiler():
    raw = {
        "dsl": {
            "strategy_kind": "timeseries",
            "market": "CN_A",
            "frequency": "D",
            "universe": {"type": "single_symbol", "symbols": ["SH600036"]},
            "rebalance": {"freq": "daily"},
            "signal": {
                "entry_rules": [
                    {
                        "lhs": {"indicator": "CLOSE"},
                        "op": ">",
                        "rhs": {"value": 0},
                        "qlib_expr": "$close > Ref($close, 1)",
                    }
                ],
                "exit_rules": [],
            },
        },
        "strategy_kind": "timeseries",
        "assumptions": [],
        "warnings": [],
        "human_summary": "",
        "parse_confidence": 0.9,
        "python": "print('do not run')",
    }

    with pytest.raises(ValueError, match="unknown ParseResult fields"):
        parse_result_from_text(json.dumps(raw))


def test_parse_result_from_text_rejects_unknown_dsl_fields_before_compiler():
    raw = {
        "dsl": {
            "strategy_kind": "timeseries",
            "market": "CN_A",
            "frequency": "D",
            "universe": {"type": "single_symbol", "symbols": ["SH600036"]},
            "rebalance": {"freq": "daily"},
            "signal": {
                "entry_rules": [
                    {
                        "lhs": {"indicator": "CLOSE"},
                        "op": ">",
                        "rhs": {"value": 0},
                        "qlib_expr": "$close > Ref($close, 1)",
                    }
                ],
                "exit_rules": [],
            },
        },
        "strategy_kind": "timeseries",
        "assumptions": [],
        "warnings": [],
        "human_summary": "",
        "parse_confidence": 0.9,
    }

    with pytest.raises(ValueError, match="unknown dsl.signal.entry_rules"):
        parse_result_from_text(json.dumps(raw))


@pytest.mark.parametrize(
    "value",
    [
        "$close > Ref($close, 1)",
        "__import__('os').system('echo unsafe')",
    ],
)
def test_parse_result_from_text_rejects_string_expression_values(value):
    raw = {
        "dsl": {
            "strategy_kind": "timeseries",
            "market": "CN_A",
            "frequency": "D",
            "universe": {"type": "single_symbol", "symbols": ["SH600036"]},
            "rebalance": {"freq": "daily"},
            "signal": {
                "entry_rules": [
                    {
                        "lhs": {"indicator": "CLOSE"},
                        "op": ">",
                        "rhs": {"value": value},
                    }
                ],
                "exit_rules": [],
            },
        },
        "strategy_kind": "timeseries",
        "assumptions": [],
        "warnings": [],
        "human_summary": "",
        "parse_confidence": 0.9,
    }

    with pytest.raises(ValueError, match="expression value"):
        parse_result_from_text(json.dumps(raw))


def test_parse_result_from_text_rejects_rule_expression_string_params_before_compiler():
    raw = {
        "dsl": {
            "strategy_kind": "timeseries",
            "market": "CN_A",
            "frequency": "D",
            "universe": {"type": "single_symbol", "symbols": ["SH600036"]},
            "rebalance": {"freq": "daily"},
            "signal": {
                "entry_rules": [
                    {
                        "lhs": {
                            "indicator": "SMA",
                            "params": ["$close > Ref($close, 1)"],
                        },
                        "op": ">",
                        "rhs": {"value": 0},
                    }
                ],
                "exit_rules": [],
            },
        },
        "strategy_kind": "timeseries",
        "assumptions": [],
        "warnings": [],
        "human_summary": "",
        "parse_confidence": 0.9,
    }

    with pytest.raises(ValueError, match="params"):
        parse_result_from_text(json.dumps(raw))


def test_parse_result_from_text_rejects_score_indicator_alias():
    raw = {
        "dsl": {
            "strategy_kind": "cross_sectional",
            "market": "CN_A",
            "frequency": "D",
            "universe": {"type": "symbol_list", "symbols": ["SH600036", "SZ000001"]},
            "rebalance": {"freq": "monthly"},
            "selection": {
                "filters": [],
                "score": {"indicator": "RETURN_N", "params": [20]},
                "rank_order": "desc",
                "top_n": 1,
            },
            "construction": {"weighting": "equal_weight"},
        },
        "strategy_kind": "cross_sectional",
        "assumptions": [],
        "warnings": [],
        "human_summary": "",
        "parse_confidence": 0.9,
    }

    with pytest.raises(ValueError, match="unknown dsl.selection.score fields"):
        parse_result_from_text(json.dumps(raw))


def test_parse_result_from_text_rejects_score_dict_params_repair():
    raw = {
        "dsl": {
            "strategy_kind": "cross_sectional",
            "market": "CN_A",
            "frequency": "D",
            "universe": {"type": "symbol_list", "symbols": ["SH600036", "SZ000001"]},
            "rebalance": {"freq": "monthly"},
            "selection": {
                "filters": [],
                "score": {"factor": "RETURN_N", "params": {"n": 20}},
                "rank_order": "desc",
                "top_n": 1,
            },
            "construction": {"weighting": "equal_weight"},
        },
        "strategy_kind": "cross_sectional",
        "assumptions": [],
        "warnings": [],
        "human_summary": "",
        "parse_confidence": 0.9,
    }

    with pytest.raises(ValueError, match="score.params"):
        parse_result_from_text(json.dumps(raw))


def test_unsupported_minute_strategy_is_rejected_without_compilable_dsl():
    result = parse_strategy("招商银行5分钟均线上穿20分钟均线买入。", fallback=False)

    assert result.dsl == {}
    assert result.strategy_kind == "unsupported"
    assert result.parse_confidence < 0.5
    assert any("分钟" in warning or "minute" in warning.lower() for warning in result.warnings)
    with pytest.raises(Exception):
        compile_strategy(result.dsl)


def test_limited_fallback_emits_explicit_warning_when_api_settings_missing():
    parser = StrategyParser(
        Settings(llm_api_base=None, llm_api_key=None, llm_model=None),
    )

    result = parser.parse("招商银行600036，5日均线上穿20日均线买入，跌破10日均线卖出。")

    assert result.strategy_kind == "timeseries"
    assert any("fallback" in warning.lower() for warning in result.warnings)
    assert validate_dsl(result.dsl)["universe"]["symbols"] == ["SH600036"]


def test_limited_fallback_does_not_fabricate_ma_for_unrelated_supported_text():
    parser = StrategyParser(
        Settings(llm_api_base=None, llm_api_key=None, llm_model=None),
    )

    result = parser.parse("招商银行600036，RSI低于30买入，高于70卖出。")

    assert result.dsl == {}
    assert result.strategy_kind == "unsupported"
    assert any("fallback" in warning.lower() for warning in result.warnings)
