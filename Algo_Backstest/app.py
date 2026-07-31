"""
Author: Vladimir Kukharev
Date: 2026-07-31
Version: 1.1
<APP> is responsible for the Streamlit web interface of the Algo Backtest
and initiates the backtest process. It handles user inputs, displays and
the interactive feedback of the results.

"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

import datetime
from strategy import get_data, compute_signals, run_backtest

# ── Page config ─────────────────────────────────────────────────────
st.set_page_config(
    page_title = "Algo Backtester",
    page_icon = "📈",
    layout = "wide",
)

# ──CSS Styles───────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;500&display=swap');

    html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
    h1, h2, h3 { font-family: 'IBM Plex Mono', monospace; letter-spacing: -0.02em; }

    .metric-card {
        background: #0f1117;
        border: 1px solid #2a2d3a;
        border-radius: 6px;
        padding: 1rem 1.25rem;
        text-align: center;
    }
    .metric-label { font-size: 0.7rem; color: #6b7280; text-transform: uppercase; letter-spacing: 0.08em; }
    .metric-value { font-family: 'IBM Plex Mono', monospace; font-size: 1.6rem; font-weight: 600; color: #e5e7eb; }
    .metric-value.positive { color: #34d399; }
    .metric-value.negative { color: #f87171; }

    div[data-testid="stDataFrame"] { border: 1px solid #2a2d3a; border-radius: 6px; }

    /* Pull sidebar content upward */
    section[data-testid="stSidebar"] > div:first-child {
        padding-top: 1rem;
    }

    /* Strategy selector pills */
    div[data-testid="stRadio"] > div {
        display: flex;
        gap: 0.5rem;
        flex-direction: row !important;
    }
    div[data-testid="stRadio"] label {
        background: #1f2937;
        border: 1px solid #374151;
        border-radius: 6px;
        padding: 0.4rem 1rem;
        cursor: pointer;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.85rem;
        color: #9ca3af;
        transition: all 0.15s;
    }
    div[data-testid="stRadio"] label:hover { border-color: #6366f1; color: #e5e7eb; }

    /* About expander styling */
    details summary { font-family: 'IBM Plex Mono', monospace; font-size: 0.8rem; }

    /* Compact ticker shortcut buttons */
    [data-testid="stSidebar"] details [data-testid="stButton"] button {
        padding: 0.15rem 0.5rem;
        font-size: 0.75rem;
        min-height: 0;
        height: auto;
        line-height: 1.4;
    }
    [data-testid="stSidebar"] details [data-testid="stButton"] {
        margin-bottom: -0.45rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Bot metadata ─────────────────────────────────────────────────────────
BOT_INFO = {
    "UT Bot": {
        "subtitle": "ATR Trailing Stop · Trend-following · Daily bars",
        "accent":   "#6366f1",
        "fill":     "rgba(99,102,241,0.08)",
        "about": (
            "**UT Bot** uses an ATR-based trailing stop to define dynamic support and resistance "
            "in real time. A buy signal fires the moment price crosses *above* the trailing stop "
            "from below — indicating a shift from bearish to bullish structure. A sell signal fires "
            "on the reverse crossover.\n\n"
            "**Why it works:** Rather than predicting direction, UT Bot reacts to confirmed momentum "
            "shifts. The ATR component scales automatically to each asset's volatility, so the same "
            "parameters work across low-vol equities and high-vol crypto without manual re-tuning. "
            "Sensitivity controls how tightly the stop trails — lower values catch more moves, higher "
            "values filter out noise and reduce whipsaws."
        ),
    },
    "V Bot": {
        "subtitle": "Coming soon — strategy under development",
        "accent":   "#f59e0b",
        "fill":     "rgba(245,158,11,0.08)",
        "about": (
            "**V Bot** is currently under development."
        ),
    },
}

# ── Header ─────────────────────────────────────────────────────────────────
st.markdown("## Algo Backtester")
st.markdown(
    "<p style='color:#6b7280;margin-top:-0.5rem;font-size:0.9rem;'>"
    "Select a strategy, configure parameters, and run a 3-month backtest."
    "</p>",
    unsafe_allow_html=True,
)
st.divider()

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:

    # Strategy selector
    st.markdown("### Strategy")
    strategy = st.radio(
        "strategy_radio",
        options=list(BOT_INFO.keys()),
        label_visibility="collapsed",
        horizontal=True,
    )

    info = BOT_INFO[strategy]

    # About expander directly below the selector
    with st.expander(f"ℹ️  About {strategy}"):
        st.markdown(info["about"])

    st.divider()
    st.markdown("### Parameters")

    COMMON_TICKERS = {
        "🇺🇸 US Large Cap": ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "BRK-B"],
        "📊 ETFs":          ["SPY", "QQQ", "EFA", "VWO", "IWM", "GLD"],
        "🏦 Finance":       ["JPM", "GS", "BAC", "MS"],
        "⚡ Energy":        ["XOM", "CVX", "BP", "SHEL"],
        "₿ Crypto":        ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD"],
    }

    # Seed the text input from a button pick if one was just made
    if "_ticker_pick" in st.session_state:
        st.session_state["_ticker_input"] = st.session_state.pop("_ticker_pick")

    if "_ticker_input" not in st.session_state:
        st.session_state["_ticker_input"] = "AAPL"

    ticker = st.text_input(
        "Ticker symbol",
        key="_ticker_input",
        placeholder="e.g. AAPL, BTC-USD, 0700.HK",
        help="Type any yfinance-supported symbol. Use the list below for common picks.",
    ).upper().strip()

    with st.expander("📋 Common symbols"):
        for group, symbols in COMMON_TICKERS.items():
            st.markdown(f"<p style='color:#6b7280;font-size:0.72rem;margin:0.6rem 0 0.3rem;text-transform:uppercase;letter-spacing:0.06em;'>{group}</p>", unsafe_allow_html=True)
            for sym in symbols:
                if st.button(sym, key=f"sym_{sym}", width='stretch'):
                    st.session_state["_ticker_pick"] = sym
                    st.rerun()

    atr_period = st.slider(
        "ATR Period",
        min_value=1, max_value=50, value=10,
        help="Lookback window for Average True Range calculation.",
    )

    sensitivity = st.slider(
        "Sensitivity (key value)",
        min_value=0.1, max_value=5.0, value=1.0, step=0.1,
        help="Multiplier applied to ATR. Higher = wider stops, fewer signals.",
    )

    run_btn = st.button("▶  Run Backtest", width='stretch', type="primary",
                        disabled=(strategy == "V Bot"))

# ── Main header updates with selected strategy ───────────────────────────────
accent = info["accent"]
st.markdown(
    f"<span style='font-family:IBM Plex Mono;font-size:1.1rem;color:{accent};font-weight:600;'>"
    f"● {strategy}</span>"
    f"<span style='color:#6b7280;font-size:0.85rem;margin-left:0.75rem;'>{info['subtitle']}</span>",
    unsafe_allow_html=True,
)
st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

# ── V Bot placeholder ───────────────────────────────────────────────────────
if strategy == "V Bot":
    st.info("**V Bot** strategy is not yet available. Select **UT Bot** to run a backtest.")
    st.stop()

# ── Guards ─────────────────────────────────────────────────────────────────────
if not ticker:
    st.warning("Please enter a ticker symbol before running the backtest.")
    st.stop()

# ── Run backtest on button click, persist results across reruns ───────────────
if run_btn:
    try:
        end_date   = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=92)
        df_raw = get_data(ticker, start=str(start_date), end=str(end_date), interval="1d")
        if df_raw.empty or len(df_raw) < 20:
            st.error(f"No data found for **{ticker}**. Double-check the symbol and try again.")
            st.stop()
    except st.errors.StopException:
        raise
    except Exception as e:
        st.error(f"Failed to fetch data for **{ticker}**: {e}")
        st.stop()

    with st.spinner("Computing signals…"):
        df_sig  = compute_signals(df_raw, atr_period=atr_period, sensitivity=sensitivity)
        results = run_backtest(df_sig)

    st.session_state["df_sig"]   = df_sig
    st.session_state["results"]  = results
    st.session_state["ticker"]   = ticker
    st.session_state["strategy"] = strategy

# Nothing run yet this session — guard must cover ALL keys before any access
_required = ("results", "df_sig", "ticker", "strategy")
if not all(k in st.session_state for k in _required):
    st.info("Configure parameters in the sidebar and click **▶ Run Backtest**.")
    st.stop()

# Pull persisted results (survives toggle/button reruns)
df_sig  = st.session_state["df_sig"]
results = st.session_state["results"]
ticker  = st.session_state["ticker"]

equity  = results["equity"]
trades  = results["trades"]
metrics = results["metrics"]

# ── Metric cards ─────────────────────────────────────────────────────────────
def metric_card(col, label: str, value: str, positive: bool | None = None):
    cls = ""
    if positive is True:  cls = "positive"
    if positive is False: cls = "negative"
    col.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value {cls}">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

c1, c2, c3 = st.columns(3)
total_ret = metrics["Total Return (%)"]
metric_card(c1, "Total Return", f"{total_ret:+.2f}%", positive=total_ret >= 0)
metric_card(c2, "Total Trades", str(metrics["Total Trades"]))
metric_card(c3, "Win Rate",     f"{metrics['Win Rate (%)']}%",
            positive=metrics["Win Rate (%)"] >= 50)

st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)

#── Equity curve ──────────────────────────────────────────────────────────────
show_bh = st.toggle("Show Buy & Hold (raw price)", value=False)

fig = go.Figure()

fig.add_trace(
    go.Scatter(
        x=equity.index,
        y=equity.values,
        mode="lines",
        name=strategy,
        line=dict(color=accent, width=2),
        fill="tozeroy",
        fillcolor=info["fill"],
    )
)

if show_bh:
    buy_hold = df_sig["Close"] / df_sig["Close"].iloc[0]
    fig.add_trace(
        go.Scatter(
            x=buy_hold.index,
            y=buy_hold.values,
            mode="lines",
            name="Buy & Hold",
            line=dict(color="#facc15", width=2, dash="dot"),
            #yellow dotted line to display nominal stock price
        )
    )

fig.add_hline(y=1.0, line=dict(color="#374151", width=1, dash="dot"))
# Horizontal line to indicate starting point

buy_dates  = df_sig[df_sig["Buy"]].index
sell_dates = df_sig[df_sig["Sell"]].index

# guards to avoid errors when there are no signals
if not buy_dates.empty:
    fig.add_trace(go.Scatter(
        x=buy_dates, y=equity.reindex(buy_dates).values,
        mode="markers", name="Buy",
        marker=dict(symbol="triangle-up", color="#34d399", size=10),
    ))

if not sell_dates.empty:
    fig.add_trace(go.Scatter(
        x=sell_dates, y=equity.reindex(sell_dates).values,
        mode="markers", name="Sell",
        marker=dict(symbol="triangle-down", color="#f87171", size=10),
    ))

# match layout to dark theme and add labels
fig.update_layout(
    title=dict(
        text=f"{ticker} · {strategy} · Indexed Equity Curve (3 months)",
        font=dict(family="IBM Plex Mono", size=14, color="#e5e7eb"),
    ),
    paper_bgcolor="#0f1117",
    plot_bgcolor="#0f1117",
    font=dict(color="#9ca3af", family="IBM Plex Sans"),
    xaxis=dict(gridcolor="#1f2937", showgrid=True, zeroline=False),
    yaxis=dict(gridcolor="#1f2937", showgrid=True, zeroline=False,
               tickformat=".3f", title="Equity (indexed to 1.0)",
               range=[0.5, 1.5]),
    legend=dict(bgcolor="rgba(0,0,0,0)", borderwidth=0),
    margin=dict(l=10, r=10, t=50, b=10),
    height=420,
)

st.plotly_chart(fig, width='stretch')

# ── Trades table ───────────────────────────────────────────────────────────────
st.markdown("### Trade Log")

if trades.empty:
    st.warning("No trades were generated with these settings over the 3-month window. "
               "Try lowering the sensitivity or ATR period.")
else:
    display = trades.copy()
    display["Entry Date"] = pd.to_datetime(display["Entry Date"]).dt.strftime("%Y-%m-%d")
    display["Exit Date"]  = pd.to_datetime(display["Exit Date"]).dt.strftime("%Y-%m-%d")

    def color_return(val):
        if isinstance(val, float):
            color = "#34d399" if val >= 0 else "#f87171"
            return f"color: {color}"
        return ""

    styled = (
        display.style
        .map(color_return, subset=["Return (%)"])
        .format({"Entry Price": "${:.2f}", "Exit Price": "${:.2f}", "Return (%)": "{:+.2f}%"})
        .set_properties(**{"background-color": "#0f1117", "color": "#e5e7eb"})
        .set_table_styles([{"selector": "th", "props": [
            ("background-color", "#1f2937"), ("color", "#9ca3af"),
            ("font-family", "IBM Plex Mono"), ("font-size", "0.75rem"),
            ("text-transform", "uppercase"), ("letter-spacing", "0.06em"),
        ]}])
    )
    st.dataframe(styled, width='stretch', hide_index=True)

st.markdown(
    "<p style='color:#374151;font-size:0.75rem;text-align:center;margin-top:2rem;'>"
    "For informational use only. Not financial advice."
    "</p>",
    unsafe_allow_html=True,
)