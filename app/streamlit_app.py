from __future__ import annotations

from datetime import date
from pathlib import Path
import sys
from typing import Any

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.backend_adapter import parse_strategy, run_backtest
from app.style import load_global_css, render_hero
from app.ui_components import (
    render_backtest_report_header,
    render_core_metric_strip,
    render_drawdown_chart,
    render_equity_chart,
    render_error_panel,
    render_input_header,
    render_parse_result,
    render_positions_table,
    render_price_trade_chart,
    render_rebalance_table,
    render_report_section_header,
    render_strategy_dsl,
    render_strategy_summary,
    render_trades_table,
)
from app.utils import (
    normalize_and_validate_symbol,
    parse_and_validate_symbol_list,
    to_date_string,
    validate_business_dates,
)


st.set_page_config(
    page_title="NLTrader",
    layout="wide",
    initial_sidebar_state="collapsed",
)


TIMESERIES_DEFAULT_STRATEGY = "5日均线上穿20日均线且成交量大于20日均量1.5倍时买入，跌破10日均线或亏损8%卖出"
CROSS_SECTIONAL_DEFAULT_STRATEGY = "每月调仓，在股票池中选择过去20日涨幅最高的10只股票等权持有"

PRESET_POOLS = {
    "核心资产池": [
        "SH600036",
        "SZ000001",
        "SH600519",
        "SZ300750",
        "SH601318",
        "SH600276",
        "SH600030",
        "SZ000858",
        "SH601899",
        "SZ002415",
        "SH600900",
        "SZ002594",
    ],
    "沪深300样本池": [
        "SH600000",
        "SH600009",
        "SH600016",
        "SH600028",
        "SH600030",
        "SH600036",
        "SH600050",
        "SH600276",
        "SH600519",
        "SH601318",
        "SH601398",
        "SZ000001",
        "SZ000002",
        "SZ000858",
        "SZ002415",
    ],
    "中证500样本池": [
        "SH600008",
        "SH600021",
        "SH600038",
        "SH600079",
        "SH600118",
        "SH600160",
        "SH600171",
        "SH600208",
        "SZ000156",
        "SZ000400",
        "SZ000513",
        "SZ002001",
        "SZ002007",
        "SZ300014",
        "SZ300059",
    ],
}


def main() -> None:
    load_global_css()
    render_hero()

    tab_timeseries, tab_cross_sectional = st.tabs(["单股时序策略", "股票池横截面策略"])
    with tab_timeseries:
        _render_timeseries_tab()
    with tab_cross_sectional:
        _render_cross_sectional_tab()


def _render_timeseries_tab() -> None:
    strategy_text, symbol, start_date, end_date, initial_cash, parse_clicked, run_clicked = _render_timeseries_input()
    current_parse_signature = _timeseries_parse_signature(strategy_text, symbol)
    current_run_signature = _run_signature(current_parse_signature, start_date, end_date, initial_cash)

    if parse_clicked:
        _parse_timeseries(strategy_text, symbol, current_parse_signature)

    if run_clicked:
        _run_timeseries(strategy_text, symbol, start_date, end_date, initial_cash, current_parse_signature, current_run_signature)

    _render_change_notices("timeseries", current_parse_signature, current_run_signature)
    _render_stored_error("timeseries")

    parse_result = st.session_state.get("timeseries_parse_result")
    backtest_result = st.session_state.get("timeseries_backtest_result")
    if parse_result:
        render_parse_result(parse_result)

    if backtest_result:
        _render_timeseries_report(parse_result or {}, backtest_result)
    if parse_result:
        render_strategy_dsl(parse_result.get("dsl", {}))


def _render_cross_sectional_tab() -> None:
    command = _render_cross_sectional_input()
    strategy_text, pool_source, preset_name, manual_symbols_text, start_date, end_date, initial_cash, parse_clicked, run_clicked = command
    universe, pool_error = _resolve_universe(pool_source, preset_name, manual_symbols_text)
    current_parse_signature = _cross_sectional_parse_signature(strategy_text, universe)
    current_run_signature = _run_signature(current_parse_signature, start_date, end_date, initial_cash)

    if parse_clicked:
        if pool_error:
            _store_error("cross_sectional", "输入错误", pool_error)
        else:
            _parse_cross_sectional(strategy_text, universe, current_parse_signature)

    if run_clicked:
        if pool_error:
            _store_error("cross_sectional", "输入错误", pool_error)
        else:
            _run_cross_sectional(
                strategy_text,
                universe,
                pool_source,
                preset_name,
                start_date,
                end_date,
                initial_cash,
                current_parse_signature,
                current_run_signature,
            )

    _render_change_notices("cross_sectional", current_parse_signature, current_run_signature)
    _render_stored_error("cross_sectional")

    parse_result = st.session_state.get("cross_sectional_parse_result")
    backtest_result = st.session_state.get("cross_sectional_backtest_result")
    if parse_result:
        render_parse_result(parse_result)

    if backtest_result:
        _render_cross_sectional_report(parse_result or {}, backtest_result)
    if parse_result:
        render_strategy_dsl(parse_result.get("dsl", {}))


def _render_timeseries_input() -> tuple[str, str, date, date, float, bool, bool]:
    render_input_header(
        "自然语言策略",
        "描述交易信号、退出条件和仓位规则，系统会整理为可回测的结构化策略。",
    )
    strategy_text = st.text_area(
        "策略描述",
        value=TIMESERIES_DEFAULT_STRATEGY,
        height=118,
        key="ts_strategy",
        placeholder="例如：5日均线上穿20日均线且成交量大于20日均量1.5倍时买入，跌破10日均线或亏损8%卖出",
    )
    st.caption(f"示例：{TIMESERIES_DEFAULT_STRATEGY}")

    symbol_col, start_col, end_col, cash_col = st.columns([1.05, 1, 1, 1.1])
    with symbol_col:
        symbol = st.text_input("股票代码", value="SH600036", key="ts_symbol")
    with start_col:
        start_date = st.date_input("开始日期", value=date(2021, 1, 1), key="ts_start")
    with end_col:
        end_date = st.date_input("结束日期", value=date(2024, 12, 31), key="ts_end")
    with cash_col:
        initial_cash = st.number_input("初始资金（元）", min_value=10_000, value=1_000_000, step=10_000, key="ts_cash")

    action_col_a, action_col_b, _ = st.columns([0.95, 0.95, 4])
    with action_col_a:
        parse_clicked = st.button("解析策略", key="ts_parse", type="secondary", use_container_width=True)
    with action_col_b:
        run_clicked = st.button("运行回测", key="ts_run", type="primary", use_container_width=True)

    return strategy_text, symbol, start_date, end_date, float(initial_cash), parse_clicked, run_clicked


def _render_cross_sectional_input() -> tuple[str, str, str, str, date, date, float, bool, bool]:
    default_manual_pool = ", ".join(PRESET_POOLS["核心资产池"])
    render_input_header(
        "自然语言策略",
        "描述股票池、排序因子、选股数量和调仓频率，系统会整理为组合规则。",
    )
    strategy_text = st.text_area(
        "策略描述",
        value=CROSS_SECTIONAL_DEFAULT_STRATEGY,
        height=118,
        key="cs_strategy",
        placeholder="例如：每月调仓，在股票池中选择过去20日涨幅最高的10只股票等权持有",
    )
    st.caption(f"示例：{CROSS_SECTIONAL_DEFAULT_STRATEGY}")

    pool_source_col, preset_col, start_col, end_col, cash_col = st.columns([1.05, 1.28, 1, 1, 1.08])
    with pool_source_col:
        pool_source = st.radio("股票池来源", ["预置池", "手动输入"], horizontal=True, key="cs_pool_source")
    with preset_col:
        preset_name = st.selectbox("预置池", list(PRESET_POOLS.keys()), index=0, key="cs_preset")
    with start_col:
        start_date = st.date_input("开始日期", value=date(2021, 1, 1), key="cs_start")
    with end_col:
        end_date = st.date_input("结束日期", value=date(2024, 12, 31), key="cs_end")
    with cash_col:
        initial_cash = st.number_input("初始资金（元）", min_value=10_000, value=1_000_000, step=10_000, key="cs_cash")

    if pool_source == "手动输入":
        manual_symbols_text = st.text_area("手动输入股票池", value=default_manual_pool, height=72, key="cs_manual_pool")
        pool_check = parse_and_validate_symbol_list(manual_symbols_text)
        st.caption(
            f"识别数量：{len(pool_check['symbols'])} 只；无效代码：{len(pool_check['invalid_symbols'])} 个；重复代码：{pool_check['duplicate_count']} 个；Top-K：Top 10；调仓频率：每月"
        )
        if pool_check["invalid_symbols"]:
            st.warning("请修正无效代码：" + "、".join(pool_check["invalid_symbols"][:8]))
    else:
        manual_symbols_text = ""
        st.caption(f"识别数量：{len(PRESET_POOLS[preset_name])} 只；Top-K：Top 10；调仓频率：每月")

    action_col_a, action_col_b, _ = st.columns([0.95, 0.95, 4])
    with action_col_a:
        parse_clicked = st.button("解析策略", key="cs_parse", type="secondary", use_container_width=True)
    with action_col_b:
        run_clicked = st.button("运行回测", key="cs_run", type="primary", use_container_width=True)

    return (
        strategy_text,
        pool_source,
        preset_name,
        manual_symbols_text,
        start_date,
        end_date,
        float(initial_cash),
        parse_clicked,
        run_clicked,
    )


def _parse_timeseries(strategy_text: str, symbol: str, parse_signature: tuple[Any, ...]) -> None:
    if not strategy_text.strip():
        _store_error("timeseries", "输入错误", "中文策略不能为空。")
        return
    normalized_symbol, symbol_error = normalize_and_validate_symbol(symbol)
    if symbol_error:
        _store_error("timeseries", "输入错误", symbol_error)
        return
    try:
        with st.spinner("正在解析策略..."):
            parse_result = parse_strategy(
                strategy_text=strategy_text,
                strategy_kind="timeseries",
                context={"symbol": normalized_symbol},
            )
    except Exception as exc:
        _store_error("timeseries", "解析错误", "单股策略解析失败。", str(exc))
        return

    st.session_state["timeseries_parse_result"] = parse_result
    st.session_state["timeseries_parse_signature"] = parse_signature
    st.session_state.pop("timeseries_backtest_result", None)
    st.session_state.pop("timeseries_run_signature", None)
    st.session_state.pop("timeseries_error", None)


def _run_timeseries(
    strategy_text: str,
    symbol: str,
    start_date: date,
    end_date: date,
    initial_cash: float,
    parse_signature: tuple[Any, ...],
    run_signature: tuple[Any, ...],
) -> None:
    parse_result = st.session_state.get("timeseries_parse_result")
    if not parse_result or st.session_state.get("timeseries_parse_signature") != parse_signature:
        _store_error("timeseries", "输入错误", "请先解析当前策略，再运行回测。")
        return

    start_str = to_date_string(start_date)
    end_str = to_date_string(end_date)
    ok, message = validate_business_dates(start_str, end_str)
    if not ok:
        _store_error("timeseries", "输入错误", message)
        return
    normalized_symbol, symbol_error = normalize_and_validate_symbol(symbol)
    if symbol_error:
        _store_error("timeseries", "输入错误", symbol_error)
        return

    try:
        with st.spinner("正在运行回测..."):
            backtest_result = run_backtest(
                parse_result,
                {
                    "symbol": normalized_symbol,
                    "start_date": start_str,
                    "end_date": end_str,
                    "initial_cash": float(initial_cash),
                    "benchmark": "SH000300",
                },
            )
    except Exception as exc:
        _store_error("timeseries", "回测错误", "单股策略回测失败。", str(exc))
        return

    st.session_state["timeseries_backtest_result"] = backtest_result
    st.session_state["timeseries_run_signature"] = run_signature
    st.session_state.pop("timeseries_error", None)


def _parse_cross_sectional(strategy_text: str, universe: list[str], parse_signature: tuple[Any, ...]) -> None:
    if not strategy_text.strip():
        _store_error("cross_sectional", "输入错误", "中文策略不能为空。")
        return
    if not universe:
        _store_error("cross_sectional", "输入错误", "股票池为空，请选择预置池或输入至少一个股票代码。")
        return
    try:
        with st.spinner("正在解析策略..."):
            parse_result = parse_strategy(
                strategy_text=strategy_text,
                strategy_kind="cross_sectional",
                context={"universe": universe},
            )
    except Exception as exc:
        _store_error("cross_sectional", "解析错误", "横截面策略解析失败。", str(exc))
        return

    st.session_state["cross_sectional_parse_result"] = parse_result
    st.session_state["cross_sectional_parse_signature"] = parse_signature
    st.session_state.pop("cross_sectional_backtest_result", None)
    st.session_state.pop("cross_sectional_run_signature", None)
    st.session_state.pop("cross_sectional_error", None)


def _run_cross_sectional(
    strategy_text: str,
    universe: list[str],
    pool_source: str,
    preset_name: str,
    start_date: date,
    end_date: date,
    initial_cash: float,
    parse_signature: tuple[Any, ...],
    run_signature: tuple[Any, ...],
) -> None:
    parse_result = st.session_state.get("cross_sectional_parse_result")
    if not parse_result or st.session_state.get("cross_sectional_parse_signature") != parse_signature:
        _store_error("cross_sectional", "输入错误", "请先解析当前策略，再运行回测。")
        return

    start_str = to_date_string(start_date)
    end_str = to_date_string(end_date)
    ok, message = validate_business_dates(start_str, end_str)
    if not ok:
        _store_error("cross_sectional", "输入错误", message)
        return

    try:
        with st.spinner("正在运行回测..."):
            backtest_result = run_backtest(
                parse_result,
                {
                    "universe": universe,
                    "pool_source": pool_source,
                    "pool_name": preset_name if pool_source == "预置池" else "manual",
                    "start_date": start_str,
                    "end_date": end_str,
                    "initial_cash": float(initial_cash),
                    "benchmark": "SH000300",
                },
            )
    except Exception as exc:
        _store_error("cross_sectional", "回测错误", "横截面策略回测失败。", str(exc))
        return

    st.session_state["cross_sectional_backtest_result"] = backtest_result
    st.session_state["cross_sectional_run_signature"] = run_signature
    st.session_state.pop("cross_sectional_error", None)


def _render_timeseries_report(parse_result: dict, backtest_result: dict) -> None:
    render_backtest_report_header(backtest_result, parse_result)

    render_report_section_header("回测报告")
    overview_col, metrics_col = st.columns([1.35, 1])
    with overview_col:
        render_strategy_summary(backtest_result.get("strategy_summary", {}), parse_result)
    with metrics_col:
        render_core_metric_strip(
            backtest_result.get("metrics", {}),
            equity_curve=backtest_result.get("equity_curve", []),
            benchmark_curve=backtest_result.get("benchmark_curve", []),
        )

    render_report_section_header("交易视图")
    render_price_trade_chart(backtest_result.get("price_data", []), backtest_result.get("trades", []))

    render_report_section_header("净值与风险")
    equity_col, drawdown_col = st.columns([1, 1])
    with equity_col:
        render_equity_chart(backtest_result.get("equity_curve", []), backtest_result.get("benchmark_curve", []))
    with drawdown_col:
        render_drawdown_chart(backtest_result.get("equity_curve", []))

    render_trades_table(backtest_result.get("trades", []))


def _render_cross_sectional_report(parse_result: dict, backtest_result: dict) -> None:
    render_backtest_report_header(backtest_result, parse_result)

    render_report_section_header("回测报告")
    overview_col, metrics_col = st.columns([1.35, 1])
    with overview_col:
        render_strategy_summary(backtest_result.get("strategy_summary", {}), parse_result)
    with metrics_col:
        render_core_metric_strip(
            backtest_result.get("metrics", {}),
            equity_curve=backtest_result.get("equity_curve", []),
            benchmark_curve=backtest_result.get("benchmark_curve", []),
        )

    render_report_section_header("净值与风险")
    equity_col, drawdown_col = st.columns([1, 1])
    with equity_col:
        render_equity_chart(backtest_result.get("equity_curve", []), backtest_result.get("benchmark_curve", []))
    with drawdown_col:
        render_drawdown_chart(backtest_result.get("equity_curve", []))

    render_rebalance_table(backtest_result.get("rebalances", []))
    render_positions_table(backtest_result.get("positions_history", []))


def _resolve_universe(pool_source: str, preset_name: str, manual_symbols_text: str) -> tuple[list[str], str]:
    if pool_source == "预置池":
        return PRESET_POOLS[preset_name], ""
    pool_check = parse_and_validate_symbol_list(manual_symbols_text)
    if pool_check["invalid_symbols"]:
        return pool_check["symbols"], "手动股票池中存在无效代码，请修正后再运行。"
    if not pool_check["symbols"]:
        return [], "股票池为空，请输入至少一个股票代码。"
    return pool_check["symbols"], ""


def _timeseries_parse_signature(strategy_text: str, symbol: str) -> tuple[Any, ...]:
    normalized_symbol, _ = normalize_and_validate_symbol(symbol)
    return ("timeseries", strategy_text.strip(), normalized_symbol)


def _cross_sectional_parse_signature(strategy_text: str, universe: list[str]) -> tuple[Any, ...]:
    return ("cross_sectional", strategy_text.strip(), tuple(universe))


def _run_signature(parse_signature: tuple[Any, ...], start_date: date, end_date: date, initial_cash: float) -> tuple[Any, ...]:
    return parse_signature + (to_date_string(start_date), to_date_string(end_date), float(initial_cash), "SH000300")


def _render_change_notices(prefix: str, parse_signature: tuple[Any, ...], run_signature: tuple[Any, ...]) -> None:
    if st.session_state.get(f"{prefix}_parse_result") and st.session_state.get(f"{prefix}_parse_signature") != parse_signature:
        st.warning("策略输入已变化，请重新解析。")
        return
    if st.session_state.get(f"{prefix}_backtest_result") and st.session_state.get(f"{prefix}_run_signature") != run_signature:
        st.warning("回测参数已变化，请重新运行回测。")


def _store_error(prefix: str, error_type: str, message: str, detail: str | None = None) -> None:
    st.session_state[f"{prefix}_error"] = {"type": error_type, "message": message, "detail": detail}


def _render_stored_error(prefix: str) -> None:
    error = st.session_state.get(f"{prefix}_error")
    if not error:
        return
    if isinstance(error, dict):
        render_error_panel(error.get("type", "回测错误"), error.get("message", "策略运行失败。"), error.get("detail"))
    else:
        render_error_panel("回测错误", "策略运行失败。", str(error))


if __name__ == "__main__":
    main()
