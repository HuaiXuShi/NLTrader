from __future__ import annotations

from app.ui_components import render_html


def load_global_css() -> None:
    render_html(
        """
        <style>
        :root {
            --nl-bg: #f7f9fc;
            --nl-surface: #ffffff;
            --nl-soft: #f8fafc;
            --nl-border: #dce5f2;
            --nl-border-strong: #b8c5d8;
            --nl-text: #111827;
            --nl-muted: #64748b;
            --nl-blue: #2563eb;
            --nl-green: #16a34a;
            --nl-red: #dc2626;
        }

        * {
            box-sizing: border-box;
            letter-spacing: 0;
        }

        body,
        .stApp {
            background: var(--nl-bg);
            color: var(--nl-text);
        }

        .block-container {
            max-width: 1280px;
            padding-top: 1.2rem;
            padding-bottom: 3rem;
        }

        .nl-hero {
            padding: 0.4rem 0 1rem;
            margin-bottom: 0.5rem;
        }

        .nl-hero-kicker {
            color: var(--nl-blue);
            font-size: 0.78rem;
            font-weight: 760;
        }

        .nl-hero h1 {
            margin: 0.18rem 0 0;
            color: var(--nl-text);
            font-size: clamp(2.2rem, 4vw, 3.7rem);
            line-height: 1;
            font-weight: 850;
        }

        .nl-subtitle {
            margin-top: 0.55rem;
            color: #1f2937;
            font-size: 1.05rem;
            font-weight: 720;
        }

        .nl-description,
        .nl-panel-subtitle,
        .nl-report-subtitle {
            color: var(--nl-muted);
            font-size: 0.9rem;
            line-height: 1.58;
        }

        .nl-description {
            max-width: 820px;
            margin-top: 0.35rem;
        }

        .nl-input-header {
            margin: 0.8rem 0 0.7rem;
            padding-top: 0.15rem;
        }

        .nl-panel,
        .nl-report-header,
        .nl-parser-report {
            border: 1px solid var(--nl-border);
            background: var(--nl-surface);
            border-radius: 8px;
            padding: 1rem;
            margin: 0.9rem 0;
        }

        .nl-panel-heading,
        .nl-section-title,
        .nl-chart-title,
        .nl-table-title {
            color: var(--nl-text);
            font-size: 1.04rem;
            font-weight: 780;
            line-height: 1.25;
        }

        .nl-section-divider {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            margin: 1.25rem 0 0.55rem;
        }

        .nl-section-divider::after {
            content: "";
            height: 1px;
            flex: 1;
            background: var(--nl-border);
        }

        .nl-report-header {
            border-left: 3px solid var(--nl-blue);
            padding: 0.9rem 1rem;
        }

        .nl-report-title {
            color: var(--nl-text);
            font-size: 1.28rem;
            font-weight: 830;
            line-height: 1.2;
        }

        .nl-summary-grid,
        .nl-parse-summary-grid,
        .nl-metric-grid {
            display: grid;
            gap: 0.7rem;
        }

        .nl-summary-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
            margin-top: 0.8rem;
        }

        .nl-parse-summary-grid {
            grid-template-columns: repeat(3, minmax(0, 1fr));
            margin-top: 0.8rem;
        }

        .nl-metric-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
            margin-top: 0.8rem;
        }

        .nl-summary-item,
        .nl-metric-card {
            border: 1px solid var(--nl-border);
            border-radius: 8px;
            background: var(--nl-soft);
            padding: 0.74rem 0.8rem;
            min-height: 74px;
            overflow: hidden;
            word-break: break-word;
        }

        .nl-summary-label,
        .nl-metric-label {
            color: var(--nl-muted);
            font-size: 0.75rem;
            font-weight: 720;
        }

        .nl-summary-value {
            color: var(--nl-text);
            font-size: 0.94rem;
            font-weight: 700;
            line-height: 1.38;
            margin-top: 0.24rem;
        }

        .nl-metric-value {
            font-size: 1.3rem;
            line-height: 1.08;
            font-weight: 830;
            margin-top: 0.35rem;
        }

        .nl-metric-positive { color: var(--nl-green); }
        .nl-metric-risk { color: var(--nl-red); }
        .nl-metric-accent { color: var(--nl-blue); }

        .nl-chart-title,
        .nl-table-title {
            margin: 1rem 0 0.5rem;
        }

        label,
        div[data-testid="stWidgetLabel"] p {
            color: #334155 !important;
            font-size: 0.83rem !important;
            font-weight: 680 !important;
        }

        textarea,
        input,
        div[data-baseweb="input"] > div,
        div[data-baseweb="select"] > div {
            background-color: #ffffff !important;
            border-color: var(--nl-border-strong) !important;
            color: var(--nl-text) !important;
            border-radius: 8px !important;
        }

        textarea {
            min-height: 112px !important;
            font-size: 0.98rem !important;
            line-height: 1.52 !important;
        }

        textarea:focus,
        input:focus,
        div[data-baseweb="input"]:focus-within,
        div[data-baseweb="select"]:focus-within {
            border-color: var(--nl-blue) !important;
            box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.12) !important;
        }

        .stButton > button {
            border-radius: 8px !important;
            min-height: 2.6rem;
            font-weight: 760 !important;
            transition: border-color 0.16s ease, background 0.16s ease, transform 0.16s ease;
        }

        .stButton > button[kind="primary"] {
            border: 1px solid #1d4ed8 !important;
            background: var(--nl-blue) !important;
            color: #ffffff !important;
        }

        .stButton > button[kind="secondary"] {
            border: 1px solid var(--nl-border-strong) !important;
            background: #ffffff !important;
            color: #1f2937 !important;
        }

        .stButton > button:hover {
            transform: translateY(-1px);
            border-color: var(--nl-blue) !important;
        }

        div[data-testid="stTabs"] [role="tablist"] {
            gap: 0.35rem;
            border-bottom: 1px solid var(--nl-border);
        }

        div[data-testid="stTabs"] [role="tab"] {
            color: var(--nl-muted);
            background: transparent;
            border: 0;
            border-radius: 0;
            padding: 0.55rem 0.9rem;
            font-weight: 720;
        }

        div[data-testid="stTabs"] [aria-selected="true"] {
            color: var(--nl-blue);
            background: #ffffff;
            border-bottom: 2px solid var(--nl-blue);
        }

        div[data-testid="stRadio"] {
            margin-bottom: 0.2rem;
        }

        div[data-testid="stPlotlyChart"] {
            border: 1px solid var(--nl-border);
            border-radius: 8px;
            background: #ffffff;
            padding: 0.35rem;
        }

        div[data-testid="stDataFrame"] {
            border: 1px solid var(--nl-border);
            border-radius: 8px;
            overflow: hidden;
            background: #ffffff;
            margin-bottom: 0.6rem;
        }

        div[data-testid="stExpander"] {
            border: 1px solid var(--nl-border);
            border-radius: 8px;
            background: #ffffff;
            box-shadow: none;
        }

        div[data-testid="stExpander"] summary {
            color: var(--nl-text) !important;
            font-weight: 720;
        }

        .nl-error-panel {
            border: 1px solid rgba(220, 38, 38, 0.24);
            border-left: 4px solid var(--nl-red);
            background: #fff7f7;
            border-radius: 8px;
            padding: 0.9rem 1rem;
            margin: 0.8rem 0;
        }

        .nl-error-type {
            color: var(--nl-red);
            font-size: 0.78rem;
            font-weight: 780;
        }

        .nl-error-message {
            color: #7f1d1d;
            font-weight: 740;
            margin-top: 0.22rem;
        }

        .nl-error-guidance,
        .nl-error-detail {
            color: #991b1b;
            font-size: 0.84rem;
            margin-top: 0.34rem;
            word-break: break-word;
        }

        @media (max-width: 980px) {
            .nl-parse-summary-grid,
            .nl-summary-grid,
            .nl-metric-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }

        @media (max-width: 640px) {
            .block-container {
                padding-left: 0.85rem;
                padding-right: 0.85rem;
            }

            .nl-parse-summary-grid,
            .nl-summary-grid,
            .nl-metric-grid {
                grid-template-columns: 1fr;
            }
        }
        </style>
        """
    )


def render_hero() -> None:
    render_html(
        """
        <div class="nl-hero">
            <div class="nl-hero-kicker">自然语言量化策略平台</div>
            <h1>NLTrader</h1>
            <div class="nl-subtitle">用中文策略描述生成结构化规则，并完成可视化回测分析。</div>
            <div class="nl-description">
                系统支持自然语言策略输入、结构化解析和回测报告展示，覆盖单股时序策略与股票池横截面策略两类研究路径。
            </div>
        </div>
        """
    )
