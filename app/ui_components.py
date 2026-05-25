from __future__ import annotations

import html
import re
import textwrap
from typing import Any

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from app.utils import format_number, format_percent, json_safe, safe_dataframe


PLOT_COLORS = {
    "paper": "#ffffff",
    "plot": "#ffffff",
    "grid": "rgba(15, 23, 42, 0.08)",
    "axis": "rgba(15, 23, 42, 0.18)",
    "font": "#111827",
    "muted": "#64748b",
    "close": "#0f2a44",
    "blue": "#2563eb",
    "orange": "#f97316",
    "purple": "#7c3aed",
    "green": "#16a34a",
    "red": "#dc2626",
    "benchmark": "#94a3b8",
    "volume": "rgba(100, 116, 139, 0.28)",
    "volume_ma": "#3b82f6",
}


def render_html(html_text: str) -> None:
    st.markdown(textwrap.dedent(html_text).strip(), unsafe_allow_html=True)


def render_input_header(title: str, subtitle: str) -> None:
    render_html(
        f"""
        <div class="nl-input-header">
            <div class="nl-panel-heading">{html.escape(title)}</div>
            <div class="nl-panel-subtitle">{html.escape(subtitle)}</div>
        </div>
        """
    )


def render_report_section_header(title: str) -> None:
    render_html(
        f"""
        <div class="nl-section-divider">
            <div class="nl-section-title">{html.escape(title)}</div>
        </div>
        """
    )


def render_parse_result(parse_result: dict | None) -> None:
    if not parse_result:
        return

    summary_html = _parse_summary_html(parse_result)
    render_html(
        f"""
        <div class="nl-panel nl-parser-report">
            <div class="nl-panel-heading">策略解析报告</div>
            <div class="nl-parse-summary-grid">{summary_html}</div>
        </div>
        """
    )


def _parse_summary_html(parse_result: dict) -> str:
    dsl = parse_result.get("dsl", {}) or {}
    kind = parse_result.get("strategy_kind") or dsl.get("kind")
    if kind == "cross_sectional":
        universe = dsl.get("universe") or []
        score = dsl.get("score", {}) or {}
        selection = dsl.get("selection", {}) or {}
        rebalance = dsl.get("rebalance", {}) or {}
        window = score.get("window", 20)
        items = [
            ("策略类型", "股票池横截面策略"),
            ("股票池", f"{len(universe)} 只股票" if universe else "预置池或手动输入"),
            ("排序因子", f"过去 {window} 日涨幅"),
            ("选股数量", f"Top {selection.get('top_n', 10)}"),
            ("调仓频率", _translate_frequency(rebalance.get("freq", "monthly"))),
            ("权重规则", "等权持有" if dsl.get("weighting") == "equal_weight" else _display_text(dsl.get("weighting"))),
        ]
    else:
        position = dsl.get("position", {}) or {}
        target_weight = position.get("target_weight")
        weight_text = (
            f"买入后目标仓位 {format_percent(target_weight, digits=0)}，退出后目标仓位 0%"
            if target_weight is not None
            else "买入后目标仓位 100%，退出后目标仓位 0%"
        )
        items = [
            ("策略类型", "单股时序策略"),
            ("交易标的", _display_text(dsl.get("symbol"))),
            ("入场条件", "SMA5 上穿 SMA20，且成交量大于 20 日均量的 1.5 倍"),
            ("出场条件", "收盘价跌破 SMA10，或触发 8% 止损"),
            ("仓位规则", weight_text),
            ("风控条件", "8% 止损"),
        ]

    return "".join(
        f"""
        <div class="nl-summary-item">
            <div class="nl-summary-label">{html.escape(label)}</div>
            <div class="nl-summary-value">{html.escape(value)}</div>
        </div>
        """
        for label, value in items
    )


def render_backtest_report_header(backtest_result: dict | None, parse_result: dict | None) -> None:
    result = backtest_result or {}
    summary = result.get("strategy_summary", {}) or {}
    kind = summary.get("strategy_kind") or (parse_result or {}).get("strategy_kind") or "-"
    if kind == "cross_sectional":
        title = "股票池动量选股策略"
        kind_label = "股票池横截面策略"
    else:
        title = f"{summary.get('symbol', '单股')} 均线交易策略"
        kind_label = "单股时序策略"
    date_range = str(summary.get("date_range", "-"))
    render_html(
        f"""
        <div class="nl-report-header">
            <div class="nl-report-title">{html.escape(title)}</div>
            <div class="nl-report-subtitle">{html.escape(kind_label)} · {html.escape(date_range)}</div>
        </div>
        """
    )


def render_strategy_summary(strategy_summary: dict | None, parse_result: dict | None = None) -> None:
    summary = strategy_summary or {}
    kind = summary.get("strategy_kind") or (parse_result or {}).get("strategy_kind") or "-"
    if kind == "cross_sectional":
        items = [
            ("策略类型", "股票池横截面策略"),
            ("股票池规模", _display_value(summary.get("universe_size"))),
            ("选股数量", f"Top {summary.get('top_n')}" if summary.get("top_n") else "Top 10"),
            ("调仓频率", _translate_frequency(summary.get("rebalance_freq", "monthly"))),
            ("回测区间", _display_value(summary.get("date_range"))),
        ]
    else:
        items = [
            ("策略类型", "单股时序策略"),
            ("交易标的", _display_value(summary.get("symbol"))),
            ("完整交易轮次", _display_value(summary.get("completed_round_trips"))),
            ("回测区间", _display_value(summary.get("date_range"))),
        ]

    render_html(
        f"""
        <div class="nl-panel">
            <div class="nl-panel-heading">策略概览</div>
            <div class="nl-summary-grid">{_summary_item_html(items)}</div>
        </div>
        """
    )


def render_core_metric_strip(
    metrics: dict | None,
    equity_curve: list[dict] | None = None,
    benchmark_curve: list[dict] | None = None,
) -> None:
    enriched = _add_benchmark_metrics(metrics or {}, equity_curve, benchmark_curve)
    items = [
        ("总收益", _format_metric_value(enriched.get("total_return"), "percent"), "positive"),
        ("年化收益", _format_metric_value(enriched.get("annualized_return"), "percent"), "positive"),
        ("最大回撤", _format_metric_value(enriched.get("max_drawdown"), "percent"), "risk"),
        ("Sharpe", _format_metric_value(enriched.get("sharpe"), "number"), "accent"),
    ]
    item_html = "".join(
        f"""
        <div class="nl-metric-card">
            <div class="nl-metric-label">{html.escape(label)}</div>
            <div class="nl-metric-value nl-metric-{html.escape(tone)}">{html.escape(value)}</div>
        </div>
        """
        for label, value, tone in items
    )
    render_html(
        f"""
        <div class="nl-panel">
            <div class="nl-panel-heading">核心指标</div>
            <div class="nl-metric-grid">{item_html}</div>
        </div>
        """
    )


def render_equity_chart(equity_curve: list[dict] | None, benchmark_curve: list[dict] | None = None) -> None:
    equity_df = safe_dataframe(equity_curve)
    if equity_df.empty or not {"date", "value"}.issubset(equity_df.columns):
        st.info("尚无净值曲线。")
        return

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=equity_df["date"],
            y=equity_df["value"],
            mode="lines",
            name="策略净值",
            line={"color": PLOT_COLORS["close"], "width": 3},
            hovertemplate="日期：%{x}<br>策略净值：%{y:.4f}<extra></extra>",
        )
    )

    benchmark_df = safe_dataframe(benchmark_curve)
    if not benchmark_df.empty and {"date", "value"}.issubset(benchmark_df.columns):
        fig.add_trace(
            go.Scatter(
                x=benchmark_df["date"],
                y=benchmark_df["value"],
                mode="lines",
                name="benchmark",
                line={"color": PLOT_COLORS["benchmark"], "width": 1.7, "dash": "dot"},
                opacity=0.68,
                hovertemplate="日期：%{x}<br>benchmark：%{y:.4f}<extra></extra>",
            )
        )

    apply_plotly_theme(fig, height=390)
    fig.update_yaxes(title_text="净值")
    fig.update_xaxes(title_text="日期")
    _render_plotly_panel("净值曲线", fig)


def render_drawdown_chart(equity_curve: list[dict] | None) -> None:
    equity_df = safe_dataframe(equity_curve)
    if equity_df.empty or not {"date", "value"}.issubset(equity_df.columns):
        st.info("尚无回撤曲线。")
        return

    values = pd.to_numeric(equity_df["value"], errors="coerce")
    running_max = values.cummax()
    drawdown = values / running_max - 1
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=equity_df["date"],
            y=drawdown,
            mode="lines",
            name="回撤",
            line={"color": PLOT_COLORS["red"], "width": 2},
            fill="tozeroy",
            fillcolor="rgba(220, 38, 38, 0.12)",
            hovertemplate="日期：%{x}<br>回撤：%{y:.2%}<extra></extra>",
        )
    )
    apply_plotly_theme(fig, height=320, legend=False)
    fig.update_yaxes(title_text="回撤", tickformat=".1%")
    fig.update_xaxes(title_text="日期")
    _render_plotly_panel("回撤分析", fig)


def render_price_trade_chart(price_data: list[dict] | None, trades: list[dict] | None) -> None:
    price_df = safe_dataframe(price_data)
    if price_df.empty or "date" not in price_df.columns:
        st.info("尚无价格数据。")
        return

    range_mode = st.radio("展示区间", ["最近一年", "全部区间"], horizontal=True, key="price_range_mode")
    chart_mode = st.radio("图表视图", ["收盘价", "K线"], horizontal=True, key="price_chart_mode")
    display_df = price_df.copy()
    if range_mode == "最近一年":
        display_df = display_df.tail(300)

    trade_df = safe_dataframe(trades)
    if not trade_df.empty and "date" in trade_df.columns:
        active_dates = set(display_df["date"].astype(str))
        trade_df = trade_df[trade_df["date"].astype(str).isin(active_dates)].copy()

    has_volume = {"volume", "volume_ma20"}.issubset(display_df.columns)
    fig = make_subplots(
        rows=2 if has_volume else 1,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.055,
        row_heights=[0.74, 0.26] if has_volume else [1],
    )

    has_ohlc = {"open", "high", "low", "close"}.issubset(display_df.columns)
    if chart_mode == "K线" and has_ohlc:
        fig.add_trace(
            go.Candlestick(
                x=display_df["date"],
                open=display_df["open"],
                high=display_df["high"],
                low=display_df["low"],
                close=display_df["close"],
                name="K线",
                increasing_line_color="#16a34a",
                increasing_fillcolor="rgba(22, 163, 74, 0.42)",
                decreasing_line_color="#dc2626",
                decreasing_fillcolor="rgba(220, 38, 38, 0.42)",
                text=[
                    f"日期：{row.date}<br>开：{row.open:.2f}<br>高：{row.high:.2f}<br>低：{row.low:.2f}<br>收：{row.close:.2f}"
                    for row in display_df.loc[:, ["date", "open", "high", "low", "close"]].itertuples(index=False)
                ],
                hoverinfo="text",
            ),
            row=1,
            col=1,
        )
    elif "close" in display_df.columns:
        fig.add_trace(
            go.Scatter(
                x=display_df["date"],
                y=display_df["close"],
                mode="lines",
                name="收盘价",
                line={"color": PLOT_COLORS["close"], "width": 2.5},
                hovertemplate="日期：%{x}<br>收盘价：%{y:.2f}<extra></extra>",
            ),
            row=1,
            col=1,
        )
    else:
        st.info("价格数据缺少 close 或 OHLC 字段。")
        return

    for column, label, color, width, opacity in [
        ("sma5", "SMA5", PLOT_COLORS["orange"], 1.8, 0.95),
        ("sma20", "SMA20", PLOT_COLORS["purple"], 1.8, 0.95),
    ]:
        if column in display_df.columns:
            fig.add_trace(
                go.Scatter(
                    x=display_df["date"],
                    y=display_df[column],
                    mode="lines",
                    name=label,
                    line={"color": color, "width": width},
                    opacity=opacity,
                    hovertemplate=f"日期：%{{x}}<br>{label}：%{{y:.2f}}<extra></extra>",
                ),
                row=1,
                col=1,
            )

    if not trade_df.empty and {"side", "date", "price"}.issubset(trade_df.columns):
        trade_df["reason"] = trade_df.get("reason", "").map(clean_display_reason)
        buys = trade_df[trade_df["side"] == "BUY"]
        sells = trade_df[trade_df["side"] == "SELL"]
        if not buys.empty:
            fig.add_trace(_trade_marker_trace(buys, "买入", "triangle-up", PLOT_COLORS["green"], "#dcfce7"), row=1, col=1)
        if not sells.empty:
            fig.add_trace(_trade_marker_trace(sells, "卖出", "triangle-down", PLOT_COLORS["red"], "#fee2e2"), row=1, col=1)

    if has_volume:
        fig.add_trace(
            go.Bar(
                x=display_df["date"],
                y=display_df["volume"],
                name="成交量",
                marker_color=PLOT_COLORS["volume"],
                hovertemplate="日期：%{x}<br>成交量：%{y:,}<extra></extra>",
            ),
            row=2,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=display_df["date"],
                y=display_df["volume_ma20"],
                mode="lines",
                name="20日均量",
                line={"color": PLOT_COLORS["volume_ma"], "width": 1.35},
                hovertemplate="日期：%{x}<br>20日均量：%{y:,}<extra></extra>",
            ),
            row=2,
            col=1,
        )

    apply_plotly_theme(fig, height=610 if has_volume else 500)
    fig.update_yaxes(title_text="价格", row=1, col=1)
    if has_volume:
        fig.update_yaxes(title_text="成交量", row=2, col=1, rangemode="tozero")
        fig.update_xaxes(title_text="日期", row=2, col=1)
        fig.update_xaxes(rangeslider={"visible": False}, row=1, col=1)
    else:
        fig.update_xaxes(title_text="日期", rangeslider={"visible": False}, row=1, col=1)
    _render_plotly_panel("交易视图", fig)


def render_trades_table(trades: list[dict] | None) -> None:
    df = safe_dataframe(trades)
    if df.empty:
        st.info("暂无交易记录。")
        return

    display = df.tail(50).copy()
    if "side" in display:
        display["side"] = display["side"].map({"BUY": "买入", "SELL": "卖出"}).fillna(display["side"])
    if "weight" in display:
        display["weight"] = pd.to_numeric(display["weight"], errors="coerce") * 100
    if "reason" in display:
        display["reason"] = display["reason"].map(clean_display_reason)
    display = _rename_existing_columns(
        display,
        {
            "date": "日期",
            "symbol": "股票代码",
            "side": "方向",
            "price": "价格",
            "quantity": "数量",
            "weight": "目标仓位",
            "reason": "原因",
        },
    )
    _render_dataframe_panel(
        "交易记录",
        display,
        {
            "价格": st.column_config.NumberColumn("价格", format="%.2f"),
            "数量": st.column_config.NumberColumn("数量", format="%d"),
            "目标仓位": st.column_config.NumberColumn("目标仓位", format="%.2f%%"),
        },
    )


def render_rebalance_table(rebalances: list[dict] | None) -> None:
    df = safe_dataframe(rebalances)
    if df.empty:
        st.info("暂无调仓记录。")
        return

    display = df.tail(50).copy()
    for column in ["avg_weight", "turnover"]:
        if column in display:
            display[column] = pd.to_numeric(display[column], errors="coerce") * 100
    if "reason" in display:
        display["reason"] = display["reason"].map(clean_display_reason)
    display = _rename_existing_columns(
        display,
        {
            "date": "调仓日期",
            "selected_symbols": "入选股票",
            "avg_weight": "平均权重",
            "turnover": "换手率",
            "reason": "原因",
        },
    )
    _render_dataframe_panel(
        "调仓记录",
        display,
        {
            "平均权重": st.column_config.NumberColumn("平均权重", format="%.2f%%"),
            "换手率": st.column_config.NumberColumn("换手率", format="%.2f%%"),
        },
    )


def render_positions_table(positions_history: list[dict] | None) -> None:
    df = safe_dataframe(positions_history)
    if df.empty:
        st.info("暂无持仓记录。")
        return

    display = df.tail(100).copy()
    for column in ["weight", "score"]:
        if column in display:
            display[column] = pd.to_numeric(display[column], errors="coerce") * 100
    display = _rename_existing_columns(
        display,
        {
            "date": "日期",
            "symbol": "股票代码",
            "weight": "目标权重",
            "score": "动量得分",
            "rank": "排名",
        },
    )
    _render_dataframe_panel(
        "持仓记录",
        display,
        {
            "目标权重": st.column_config.NumberColumn("目标权重", format="%.2f%%"),
            "动量得分": st.column_config.NumberColumn("动量得分", format="%.2f%%"),
            "排名": st.column_config.NumberColumn("排名", format="%d"),
        },
    )


def render_strategy_dsl(dsl: dict | None) -> None:
    with st.expander("查看策略 DSL", expanded=False):
        if dsl:
            st.json(json_safe(dsl))
        else:
            st.write("尚无 DSL。")


def render_error_panel(error_type: str, message: str, detail: str | None = None) -> None:
    guidance = {
        "输入错误": "请检查策略文本、日期区间、股票代码或股票池配置。",
        "解析错误": "请检查自然语言策略是否符合当前支持的策略类型。",
        "回测错误": "请检查回测区间、标的和股票池配置。",
        "数据错误": "请检查图表或表格所需数据字段是否存在。",
    }.get(error_type, "请检查输入内容。")
    detail_html = f'<div class="nl-error-detail">{html.escape(detail)}</div>' if detail else ""
    render_html(
        f"""
        <div class="nl-error-panel">
            <div class="nl-error-type">{html.escape(error_type)}</div>
            <div class="nl-error-message">{html.escape(message)}</div>
            <div class="nl-error-guidance">{html.escape(guidance)}</div>
            {detail_html}
        </div>
        """
    )


def apply_plotly_theme(fig: go.Figure, height: int = 420, legend: bool = True) -> None:
    fig.update_layout(
        paper_bgcolor=PLOT_COLORS["paper"],
        plot_bgcolor=PLOT_COLORS["plot"],
        font={"color": PLOT_COLORS["font"], "family": "Inter, system-ui, -apple-system, BlinkMacSystemFont, sans-serif"},
        height=height,
        margin={"l": 22, "r": 20, "t": 28, "b": 26},
        hovermode="x unified",
        showlegend=legend,
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "left",
            "x": 0,
            "font": {"color": PLOT_COLORS["font"], "size": 12},
            "title": {"text": ""},
            "bgcolor": "rgba(255, 255, 255, 0.88)",
            "bordercolor": "rgba(15, 23, 42, 0.08)",
            "borderwidth": 1,
        },
        hoverlabel={
            "bgcolor": "#111827",
            "bordercolor": "rgba(15, 23, 42, 0.12)",
            "font": {"color": "#ffffff", "size": 12},
        },
        bargap=0.12,
    )
    fig.update_xaxes(
        linecolor=PLOT_COLORS["axis"],
        gridcolor=PLOT_COLORS["grid"],
        zerolinecolor=PLOT_COLORS["grid"],
        tickfont={"color": PLOT_COLORS["muted"]},
        title_font={"color": PLOT_COLORS["font"]},
        showline=True,
        mirror=False,
    )
    fig.update_yaxes(
        linecolor=PLOT_COLORS["axis"],
        gridcolor=PLOT_COLORS["grid"],
        zerolinecolor=PLOT_COLORS["grid"],
        tickfont={"color": PLOT_COLORS["muted"]},
        title_font={"color": PLOT_COLORS["font"]},
        showline=True,
        mirror=False,
    )


def clean_display_reason(reason: Any) -> str:
    text = str(reason or "")
    text = re.sub(r"^[A-Za-z]+\s+fallback 第\s*\d+\s*轮[:：]\s*", "", text, flags=re.IGNORECASE)
    return text.strip()


def _render_plotly_panel(title: str, fig: go.Figure) -> None:
    render_html(f'<div class="nl-chart-title">{html.escape(title)}</div>')
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "responsive": True})


def _render_dataframe_panel(title: str, df: pd.DataFrame, column_config: dict | None = None) -> None:
    render_html(f'<div class="nl-table-title">{html.escape(title)}</div>')
    st.dataframe(df, use_container_width=True, hide_index=True, column_config=column_config)


def _summary_item_html(items: list[tuple[str, str]]) -> str:
    return "".join(
        f"""
        <div class="nl-summary-item">
            <div class="nl-summary-label">{html.escape(label)}</div>
            <div class="nl-summary-value">{html.escape(value)}</div>
        </div>
        """
        for label, value in items
    )


def _format_metric_value(value: Any, value_type: str) -> str:
    if value is None:
        return "—"
    if value_type == "percent":
        formatted = format_percent(value)
    elif value_type == "integer":
        formatted = format_number(value, digits=0)
    else:
        formatted = format_number(value)
    return "—" if formatted == "-" else formatted


def _display_value(value: Any) -> str:
    if value is None or value == "":
        return "暂未提供"
    return str(value)


def _display_text(value: Any, fallback: str = "暂未提供") -> str:
    if value is None or value == "":
        return fallback
    return str(value)


def _translate_frequency(value: Any) -> str:
    mapping = {
        "day": "日频",
        "daily": "日频",
        "week": "周频",
        "weekly": "周频",
        "month": "每月",
        "monthly": "每月",
    }
    return mapping.get(str(value or "").lower(), _display_text(value, "使用默认规则"))


def _rename_existing_columns(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    ordered_columns = [column for column in mapping if column in df.columns]
    remaining_columns = [column for column in df.columns if column not in ordered_columns]
    return df.loc[:, ordered_columns + remaining_columns].rename(columns=mapping)


def _add_benchmark_metrics(metrics: dict, equity_curve: list[dict] | None, benchmark_curve: list[dict] | None) -> dict:
    enriched = dict(metrics)
    if "benchmark_return" not in enriched:
        enriched["benchmark_return"] = _curve_return(benchmark_curve)
    if "excess_return" not in enriched:
        strategy_return = enriched.get("total_return")
        benchmark_return = enriched.get("benchmark_return")
        if strategy_return is not None and benchmark_return is not None:
            try:
                enriched["excess_return"] = float(strategy_return) - float(benchmark_return)
            except (TypeError, ValueError):
                enriched["excess_return"] = None
        else:
            enriched["excess_return"] = None
    if "total_return" not in enriched:
        enriched["total_return"] = _curve_return(equity_curve)
    return enriched


def _curve_return(curve: list[dict] | None) -> float | None:
    df = safe_dataframe(curve)
    if df.empty or "value" not in df.columns:
        return None
    values = pd.to_numeric(df["value"], errors="coerce").dropna()
    if len(values) < 2 or values.iloc[0] == 0:
        return None
    return float(values.iloc[-1] / values.iloc[0] - 1)


def _trade_marker_trace(df: pd.DataFrame, label: str, symbol: str, color: str, line_color: str) -> go.Scatter:
    custom = []
    for _, row in df.iterrows():
        custom.append([label, row.get("reason", "")])
    return go.Scatter(
        x=df["date"],
        y=df["price"],
        mode="markers",
        name=label,
        customdata=custom,
        marker={"color": color, "line": {"color": line_color, "width": 1.8}, "size": 16, "symbol": symbol},
        hovertemplate="日期：%{x}<br>动作：%{customdata[0]}<br>价格：%{y:.2f}<br>原因：%{customdata[1]}<extra></extra>",
    )
