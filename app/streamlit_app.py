from __future__ import annotations

import io
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

from portfolio_risk_analytics.market_data import fetch_yahoo_price_csv
from portfolio_risk_analytics.options_analytics import black_scholes
from portfolio_risk_analytics.portfolio_tracker import (
    TRADING_DAYS_PER_YEAR,
    calculate_risk_metrics,
    load_portfolio_data,
    portfolio_total_return_values,
    summarize_portfolio,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


st.set_page_config(
    page_title="Portfolio Risk Analytics",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :root {
        --ink: #e8eef8;
        --muted: #9baec4;
        --line: rgba(155, 174, 196, .16);
        --panel: rgba(18, 31, 49, .78);
        --accent: #61a8ff;
        --positive: #46d6a0;
    }
    .stApp {
        background:
          radial-gradient(ellipse at 12% 0%, rgba(49, 102, 170, .22), transparent 35%),
          linear-gradient(145deg, #0b1421 0%, #0d1725 55%, #101c2c 100%);
        color: var(--ink);
    }
    .block-container { max-width: 1500px; padding-top: 2rem; padding-bottom: 3rem; }
    [data-testid="stSidebar"] {
        background: rgba(9, 17, 28, .88);
        border-right: 1px solid var(--line);
    }
    [data-testid="stMetric"] {
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 14px;
        padding: 1rem 1.15rem;
        min-height: 118px;
    }
    [data-testid="stMetricLabel"] p { color: var(--muted); font-size: .83rem; }
    [data-testid="stMetricValue"] { color: var(--ink); font-weight: 650; }
    [data-testid="stMetricDelta"] { font-size: .8rem; }
    [data-testid="stTabs"] button[role="tab"] {
        border-radius: 9px 9px 0 0;
        padding: .7rem 1rem;
    }
    [data-testid="stTabs"] button[aria-selected="true"] {
        border-bottom-color: var(--accent);
        color: var(--accent);
    }
    div[data-testid="stDataFrame"] {
        border: 1px solid var(--line);
        border-radius: 12px;
        overflow: hidden;
    }
    .hero {
        padding: 1.2rem 0 1.35rem;
        border-bottom: 1px solid var(--line);
        margin-bottom: 1.2rem;
    }
    .eyebrow {
        color: var(--accent);
        text-transform: uppercase;
        letter-spacing: .14em;
        font-size: .72rem;
        font-weight: 700;
    }
    .hero h1 { margin: .35rem 0; font-size: 2.15rem; color: var(--ink); }
    .hero p { color: var(--muted); margin: 0; }
    .section-note { color: var(--muted); font-size: .88rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


CURRENCIES = {
    "EUR (€)": "€",
    "USD ($)": "$",
    "GBP (£)": "£",
    "CHF (CHF)": "CHF ",
    "CAD (C$)": "C$",
    "JPY (¥)": "¥",
}


@st.cache_data(ttl=300)
def _cached_yahoo_price_csv(
    symbols: list[str], quantities: list[float], start_date: date, end_date: date
) -> str:
    return fetch_yahoo_price_csv(symbols, quantities, start_date, end_date)


def _format_money(value: float | int, currency_symbol: str) -> str:
    if currency_symbol in ("€", "$", "£", "¥"):
        return f"{currency_symbol}{float(value):,.2f}"
    return f"{currency_symbol}{float(value):,.2f}"


def _correlation_style(value: float) -> str:
    if pd.isna(value):
        return "background-color: #263247; color: #edf4ff"

    value = max(-1.0, min(1.0, float(value)))
    red = (215, 48, 39)
    yellow = (255, 255, 191)
    green = (26, 152, 80)
    start, end, fraction = (
        (red, yellow, value + 1.0) if value <= 0 else (yellow, green, value)
    )
    rgb = tuple(
        round(start[channel] + fraction * (end[channel] - start[channel]))
        for channel in range(3)
    )
    return f"background-color: rgb{rgb}; color: #101828"


def _style_correlation_column(values: pd.Series) -> list[str]:
    return [_correlation_style(value) for value in values]


def _build_metrics_frame(risk, currency_code: str) -> pd.DataFrame:
    metrics = {
        "Observations": risk.observation_count,
        "Confidence level": risk.confidence_level,
        "Cumulative return": risk.cumulative_return,
        "Annualized volatility": risk.annualized_volatility,
        "EWMA volatility": risk.ewma_volatility,
        "Sharpe ratio": risk.sharpe_ratio,
        "Sortino ratio": risk.sortino_ratio,
        "Historical VaR (daily)": risk.historical_var,
        "Historical expected shortfall (daily)": risk.expected_shortfall,
        "Parametric VaR (daily)": risk.parametric_var,
        "Parametric expected shortfall (daily)": risk.parametric_expected_shortfall,
        "Maximum drawdown": risk.max_drawdown,
        "Calmar ratio": risk.calmar_ratio,
    }
    return pd.DataFrame(
        [{"Metric": name, "Value": "" if value is None else value,
          "Unit": "observations" if name == "Observations" else (
              "ratio" if "ratio" in name.lower() else (
                  "confidence" if name == "Confidence level" else "%"
              )
          ),
          "Currency": currency_code}
         for name, value in metrics.items()]
    )


st.markdown(
    """
    <div class="hero">
      <div class="eyebrow">Portfolio intelligence</div>
      <h1>Portfolio Risk Analytics</h1>
      <p>Performance, market risk and scenario analysis from your own price history.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

left_intro, right_upload = st.columns([1.2, 1], vertical_alignment="center")
with left_intro:
    st.markdown(
        "**Start with your data.** Import a CSV, explicitly load the included "
        "historical case, or request a price history from Yahoo Finance."
    )
with right_upload:
    sample_path = PROJECT_ROOT / "examples" / "sample_prices.csv"
    st.download_button(
        "Download synthetic example",
        data=sample_path.read_bytes(),
        file_name="portfolio_market_data_example.csv",
        mime="text/csv",
        width="stretch",
    )

real_case_path = PROJECT_ROOT / "examples" / "real_market_case.csv"
data_sources = ["Upload CSV"]
if real_case_path.is_file():
    data_sources.append("Included real-market case")
data_sources.append("Fetch from Yahoo Finance")
data_source = st.radio(
    "Choose a data source",
    data_sources,
    horizontal=True,
    help="No market data is loaded until you choose a source or upload a file.",
)
use_real_case = data_source == "Included real-market case"
if use_real_case:
    csv_text = real_case_path.read_text(encoding="utf-8")
    st.caption(
        "Historical US ETF data: SPY, QQQ, IWM, TLT and GLD. "
        "The included file contains 2020–2026 observations."
    )
    st.download_button(
        "Download the real-market CSV",
        data=real_case_path.read_bytes(),
        file_name="real_market_case.csv",
        mime="text/csv",
    )
elif data_source == "Fetch from Yahoo Finance":
    st.caption(
        "On-demand daily history from Yahoo Finance; no API key is required. "
        "This unofficial source may be delayed, throttled or changed and is not "
        "a live trading feed."
    )
    with st.form("yahoo_market_data_form"):
        yahoo_symbols_text = st.text_input(
            "Ticker symbols (comma-separated)", value="SPY, QQQ, IWM"
        )
        yahoo_quantities_text = st.text_input(
            "Quantity for each ticker, in the same order", value="1, 1, 1"
        )
        date_columns = st.columns(2)
        yahoo_start_date = date_columns[0].date_input(
            "Start date", value=date.today() - timedelta(days=365 * 5)
        )
        yahoo_end_date = date_columns[1].date_input(
            "End date", value=date.today()
        )
        fetch_submitted = st.form_submit_button(
            "Fetch adjusted market history", type="primary"
        )
    if fetch_submitted:
        st.session_state.pop("yahoo_market_csv", None)
        yahoo_symbols = [
            symbol.strip().upper()
            for symbol in yahoo_symbols_text.split(",")
            if symbol.strip()
        ]
        try:
            yahoo_quantities = [
                float(quantity.strip())
                for quantity in yahoo_quantities_text.split(",")
            ]
        except ValueError:
            st.error("Quantities must be comma-separated numbers.")
            st.stop()
        try:
            with st.spinner("Requesting daily prices from Yahoo Finance..."):
                st.session_state["yahoo_market_csv"] = _cached_yahoo_price_csv(
                    yahoo_symbols,
                    yahoo_quantities,
                    yahoo_start_date,
                    yahoo_end_date,
                )
        except (ValueError, RuntimeError) as error:
            st.error(f"Unable to fetch market data: {error}")
            st.stop()
    if "yahoo_market_csv" not in st.session_state:
        st.info("Set the symbols and period, then fetch the history to continue.")
        st.stop()
    csv_text = st.session_state["yahoo_market_csv"]
    st.success("Adjusted daily price history loaded.")
    st.download_button(
        "Download fetched market CSV",
        data=csv_text.encode("utf-8"),
        file_name="yahoo_adjusted_market_history.csv",
        mime="text/csv",
    )
else:
    uploaded_file = st.file_uploader(
        "Import portfolio data",
        type=["csv"],
        help="Required columns: date, symbol, close, quantity. One row per asset per date.",
        label_visibility="collapsed",
    )
    if uploaded_file is None:
        with st.expander("About the included datasets"):
            st.markdown(
                "- **Real-market stress test:** daily prices for five real ETFs from "
                "2020 onward. Select it in the data-source chooser above.\n"
                "- **Synthetic example:** tiny fictional data for checking the CSV format."
            )
            st.download_button(
                "Download synthetic example CSV",
                data=sample_path.read_bytes(),
                file_name="portfolio_market_data_example.csv",
                mime="text/csv",
            )
        st.info("Upload a CSV or explicitly load the included real-market case.")
        st.stop()
    try:
        csv_text = uploaded_file.getvalue().decode("utf-8-sig")
    except UnicodeDecodeError:
        st.error("The CSV must be encoded as UTF-8.")
        st.stop()

st.caption(
    "Required columns: date, symbol, close, quantity · ISO dates · constant quantity "
    "per asset · optional adjusted_close for dividend-adjusted returns · at least 3 dates."
)

try:
    positions, history = load_portfolio_data(io.StringIO(csv_text))
except UnicodeDecodeError:
    st.error("The CSV must be encoded as UTF-8.")
    st.stop()
except ValueError as error:
    st.error(f"Unable to analyze this CSV: {error}")
    st.stop()

with st.sidebar:
    st.markdown("### Analysis settings")
    st.caption("These assumptions affect display or risk ratios, not the source data.")
    currency_choice = st.selectbox(
        "Display currency",
        list(CURRENCIES),
        index=1 if data_source != "Upload CSV" else 0,
        help="Changes the displayed currency label only; no FX conversion is performed.",
    )
    currency_symbol = CURRENCIES[currency_choice]
    annual_risk_free_rate = st.number_input(
        "Annual risk-free rate (%)",
        min_value=0.0,
        max_value=20.0,
        value=3.0,
        step=0.25,
        help="Used in the Sharpe and Sortino ratios.",
    ) / 100
    confidence_label = st.selectbox(
        "VaR / ES confidence level",
        ["90%", "95%", "99%"],
        index=1,
        help="Sets the tail percentile for both historical and parametric estimates.",
    )
    confidence_level = float(confidence_label.strip("%")) / 100
    st.markdown("---")
    st.markdown("### Input snapshot")
    st.metric("Assets", len(positions))
    st.metric("Price observations", len(history))

summary = summarize_portfolio(positions)
risk = calculate_risk_metrics(
    positions,
    history,
    annual_risk_free_rate=annual_risk_free_rate,
    confidence_level=confidence_level,
)
if any(observation.adjusted_closing_prices is not None for observation in history):
    st.info(
        "Performance and risk returns use dividend-adjusted closes where supplied; "
        "position market values use raw closes. The currency selector does not convert FX."
    )
if len(history) < 60:
    st.warning(
        f"Short history: {len(history)} observations. Risk estimates and annualized "
        "ratios can be highly unstable; use a longer sample where possible."
    )

holdings = pd.DataFrame(
    [
        {
            "Symbol": position.symbol,
            "Quantity": float(position.quantity),
            "Initial price": float(position.purchase_price),
            "Latest price": float(position.current_price),
            "Market value": float(position.market_value),
            "P&L": float(position.unrealized_pnl),
            "Return": float(position.return_rate),
            "Weight": float(position.market_value / summary.total_market_value),
        }
        for position in summary.positions
    ]
)

portfolio_values = portfolio_total_return_values(positions, history)
observation_dates = [observation.observation_date for observation in history]
portfolio_returns = pd.Series(portfolio_values, index=observation_dates).pct_change()

summary_cols = st.columns(4)
summary_cols[0].metric(
    "Latest portfolio value", _format_money(summary.total_market_value, currency_symbol)
)
summary_cols[1].metric(
    "Initial value", _format_money(summary.total_cost_basis, currency_symbol)
)
summary_cols[2].metric(
    "Unrealized P&L",
    _format_money(summary.total_unrealized_pnl, currency_symbol),
    delta=f"{summary.total_return_rate:.2%}",
)
summary_cols[3].metric("Period return", f"{risk.cumulative_return:.2%}")

overview_tab, risk_tab, positions_tab, stress_tab, options_tab, export_tab = st.tabs(
    ["Performance", "Risk analytics", "Positions", "Stress tests", "Options", "Export"]
)

with overview_tab:
    st.subheader("Portfolio performance")
    st.caption(
        "Portfolio and asset performance, rebased to 100 at the first date. "
        "Adjusted closes include distributions when supplied."
    )
    indexed_performance = pd.DataFrame(
        {
            "Portfolio": [value / portfolio_values[0] * 100 for value in portfolio_values],
            **{
                position.symbol: [
                    float(
                        (
                            observation.adjusted_closing_prices
                            or observation.closing_prices
                        )[position.symbol]
                    )
                    / float(
                        (
                            history[0].adjusted_closing_prices
                            or history[0].closing_prices
                        )[position.symbol]
                    )
                    * 100
                    for observation in history
                ]
                for position in positions
            },
        },
        index=observation_dates,
    )
    st.line_chart(indexed_performance, width="stretch")

    chart_left, chart_right = st.columns([1.15, 1])
    with chart_left:
        st.markdown("#### Rolling 21-observation volatility")
        rolling_volatility = (
            portfolio_returns.rolling(21).std(ddof=1) * TRADING_DAYS_PER_YEAR**0.5
        )
        if rolling_volatility.notna().any():
            st.line_chart(rolling_volatility.rename("Annualized volatility"), width="stretch")
        else:
            st.info("Requires at least 22 observations for one complete rolling window.")
    with chart_right:
        st.markdown("#### Current allocation")
        st.bar_chart(holdings.set_index("Symbol")["Weight"] * 100, width="stretch")

    with st.expander("View indexed performance data"):
        st.dataframe(indexed_performance, width="stretch")

with risk_tab:
    st.subheader("Risk dashboard")
    st.caption(
        f"Tail risk estimated at {confidence_label} confidence. VaR/ES are one-observation "
        "estimates; volatility and ratios are annualized."
    )
    risk_metrics = st.columns(4)
    risk_metrics[0].metric("Annualized volatility", f"{risk.annualized_volatility:.2%}")
    risk_metrics[1].metric("EWMA volatility", f"{risk.ewma_volatility:.2%}")
    risk_metrics[2].metric(
        "Historical VaR",
        f"{risk.historical_var:.2%}",
        help="Empirical lower-tail quantile of observed portfolio returns.",
    )
    risk_metrics[3].metric(
        "Historical expected shortfall", f"{risk.expected_shortfall:.2%}"
    )

    ratio_cols = st.columns(4)
    ratio_cols[0].metric(
        "Sharpe ratio", "N/A" if risk.sharpe_ratio is None else f"{risk.sharpe_ratio:.2f}"
    )
    ratio_cols[1].metric(
        "Sortino ratio", "N/A" if risk.sortino_ratio is None else f"{risk.sortino_ratio:.2f}"
    )
    ratio_cols[2].metric("Maximum drawdown", f"{risk.max_drawdown:.2%}")
    ratio_cols[3].metric(
        "Calmar ratio", "N/A" if risk.calmar_ratio is None else f"{risk.calmar_ratio:.2f}"
    )

    st.markdown("#### Historical vs parametric tail risk")
    tail_df = pd.DataFrame(
        {
            "Historical": [risk.historical_var, risk.expected_shortfall],
            "Gaussian parametric": [
                risk.parametric_var,
                risk.parametric_expected_shortfall,
            ],
        },
        index=["VaR", "Expected shortfall"],
    )
    st.dataframe(tail_df.style.format("{:.2%}"), width="stretch")
    st.caption(
        "Parametric VaR/ES assumes normally distributed returns. Historical estimates "
        "depend on the uploaded sample and may be especially unstable for short histories."
    )

    risk_left, risk_right = st.columns(2)
    with risk_left:
        st.markdown("#### Euler risk contribution")
        if risk.risk_contribution_pct:
            contribution_df = pd.DataFrame(
                [
                    {
                        "Symbol": symbol,
                        "Annualized asset volatility": risk.asset_volatility[symbol],
                        "Risk contribution": contribution,
                    }
                    for symbol, contribution in risk.risk_contribution_pct.items()
                ]
            ).set_index("Symbol")
            st.dataframe(
                contribution_df.style.format("{:.2%}"),
                width="stretch",
            )
            st.caption("Negative contributions indicate an estimated hedge/diversification effect.")
        else:
            st.info("Risk contributions are undefined when portfolio covariance is zero.")
    with risk_right:
        st.markdown("#### Correlation matrix")
        correlation_df = pd.DataFrame.from_dict(risk.correlation_matrix, orient="index")
        if not correlation_df.empty:
            st.dataframe(
                correlation_df.style.format(
                    lambda value: "N/A" if pd.isna(value) else f"{value:.2f}"
                ).apply(_style_correlation_column, axis=0),
                width="stretch",
            )

with positions_tab:
    st.subheader("Holdings and contribution to portfolio value")
    st.caption(
        "Position values and P&L use raw closing prices. "
        "Performance/risk returns use adjusted closes when the file includes them."
    )
    display_holdings = holdings.copy()
    display_holdings["Initial price"] = display_holdings["Initial price"].map(
        lambda value: _format_money(value, currency_symbol)
    )
    display_holdings["Latest price"] = display_holdings["Latest price"].map(
        lambda value: _format_money(value, currency_symbol)
    )
    display_holdings["Market value"] = display_holdings["Market value"].map(
        lambda value: _format_money(value, currency_symbol)
    )
    display_holdings["P&L"] = display_holdings["P&L"].map(
        lambda value: _format_money(value, currency_symbol)
    )
    display_holdings["Return"] = display_holdings["Return"].map(
        lambda value: f"{value:.2%}"
    )
    display_holdings["Weight"] = display_holdings["Weight"].map(
        lambda value: f"{value:.2%}"
    )
    st.dataframe(display_holdings, width="stretch", hide_index=True)
    st.caption(
        "Display currency is a label only. The app does not convert currency or infer "
        "the denomination of uploaded prices."
    )

with stress_tab:
    st.subheader("Instantaneous price-shock scenarios")
    st.caption(
        "Apply hypothetical shocks to current market values. This is a static sensitivity "
        "analysis, not a forecast, VaR model or historical simulation."
    )
    preset_shocks = [-30, -20, -10, -5, 0, 5, 10]
    preset_results = []
    latest_market_values = {
        position.symbol: float(position.market_value) for position in positions
    }
    for shock_pct in preset_shocks:
        impact = sum(
            market_value * shock_pct / 100
            for market_value in latest_market_values.values()
        )
        stressed_value = float(summary.total_market_value) + impact
        preset_results.append(
            {
                "Parallel shock": f"{shock_pct:+d}%",
                "P&L impact": impact,
                "Stressed portfolio value": stressed_value,
                "Return vs current": impact / float(summary.total_market_value),
            }
        )
    preset_df = pd.DataFrame(preset_results)
    st.dataframe(
        preset_df.style.format(
            {
                "P&L impact": lambda value: _format_money(value, currency_symbol),
                "Stressed portfolio value": lambda value: _format_money(value, currency_symbol),
                "Return vs current": "{:.2%}".format,
            }
        ),
        width="stretch",
        hide_index=True,
    )

    st.markdown("#### Build a custom scenario")
    st.caption("Set an independent price shock for each holding.")
    custom_shocks: dict[str, float] = {}
    shock_columns = st.columns(min(3, len(positions)))
    for index, position in enumerate(positions):
        with shock_columns[index % len(shock_columns)]:
            custom_shocks[position.symbol] = st.slider(
                f"{position.symbol} shock (%)",
                min_value=-100,
                max_value=100,
                value=0,
                step=5,
                key=f"shock_{position.symbol}",
            )
    custom_impact = sum(
        latest_market_values[symbol] * shock / 100
        for symbol, shock in custom_shocks.items()
    )
    stressed_total = float(summary.total_market_value) + custom_impact
    result_left, result_mid, result_right = st.columns(3)
    result_left.metric("Scenario P&L", _format_money(custom_impact, currency_symbol))
    result_mid.metric(
        "Stressed value", _format_money(stressed_total, currency_symbol)
    )
    result_right.metric(
        "Change vs current",
        f"{custom_impact / float(summary.total_market_value):.2%}",
    )
    shock_contributions = pd.DataFrame(
        [
            {
                "Symbol": symbol,
                "Shock": f"{shock:+.0f}%",
                "Scenario P&L": latest_market_values[symbol] * shock / 100,
            }
            for symbol, shock in custom_shocks.items()
        ]
    )
    st.dataframe(
        shock_contributions.style.format(
            {"Scenario P&L": lambda value: _format_money(value, currency_symbol)}
        ),
        width="stretch",
        hide_index=True,
    )

with options_tab:
    st.subheader("European option pricing and sensitivity")
    st.caption(
        "Black–Scholes theoretical valuation, Greeks and what-if scenarios. "
        "Volatility defaults to the underlying's historical estimate, not implied "
        "volatility. This is not an exchange option-chain quote; the currency "
        "selector is a label and does not convert FX."
    )
    option_symbols = [position.symbol for position in positions]
    option_position = st.selectbox("Underlying asset", option_symbols)
    underlying_position = next(
        position for position in positions if position.symbol == option_position
    )
    option_left, option_mid, option_right = st.columns(3)
    option_spot = option_left.number_input(
        "Underlying spot price",
        min_value=0.01,
        value=float(underlying_position.current_price),
        step=max(0.01, round(float(underlying_position.current_price) * 0.01, 2)),
        format="%.4f",
        key=f"option_spot_{option_position}",
        help="Defaults to the latest raw close in the selected portfolio data.",
    )
    option_strike = option_mid.number_input(
        "Strike price",
        min_value=0.01,
        value=float(underlying_position.current_price),
        step=max(0.01, round(float(underlying_position.current_price) * 0.01, 2)),
        format="%.4f",
        key=f"option_strike_{option_position}",
    )
    expiry_days = option_right.number_input(
        "Calendar days to expiry",
        min_value=1,
        max_value=3650,
        value=90,
        step=1,
    )
    option_left, option_mid, option_right = st.columns(3)
    option_type = option_left.selectbox("Contract type", ["Call", "Put"]).lower()
    historical_volatility = risk.asset_volatility.get(option_position, 0.25)
    volatility_percent = option_mid.number_input(
        "Annualized volatility (%)",
        min_value=0.1,
        max_value=500.0,
        value=min(500.0, max(0.1, historical_volatility * 100.0)),
        step=1.0,
        key=f"option_volatility_{option_position}",
        help="Defaults to historical realized volatility; replace it with implied volatility if you have a market estimate.",
    )
    dividend_yield_percent = option_right.number_input(
        "Continuous dividend yield (%)",
        min_value=0.0,
        max_value=50.0,
        value=0.0,
        step=0.25,
        help="Enter an estimate; it is not inferred from the historical CSV.",
    )
    option_left, option_mid, option_right = st.columns(3)
    option_side = option_left.selectbox("Position", ["Long", "Short"])
    contract_count = option_mid.number_input(
        "Number of contracts", min_value=1, max_value=10000, value=1, step=1
    )
    contract_multiplier = option_right.number_input(
        "Shares per contract", min_value=1, max_value=10000, value=100, step=1
    )

    valuation = black_scholes(
        spot=option_spot,
        strike=option_strike,
        time_to_expiry_years=float(expiry_days) / 365.0,
        volatility=volatility_percent / 100.0,
        risk_free_rate=annual_risk_free_rate,
        dividend_yield=dividend_yield_percent / 100.0,
        option_type=option_type,
    )
    position_sign = 1 if option_side == "Long" else -1
    contract_scale = int(contract_count) * int(contract_multiplier)
    premium_per_contract = valuation.theoretical_price * int(contract_multiplier)
    intrinsic_value = (
        max(option_spot - option_strike, 0.0)
        if option_type == "call"
        else max(option_strike - option_spot, 0.0)
    )
    breakeven = (
        option_strike + valuation.theoretical_price
        if option_type == "call"
        else option_strike - valuation.theoretical_price
    )
    option_metrics = st.columns(4)
    option_metrics[0].metric(
        "Model premium / share",
        _format_money(valuation.theoretical_price, currency_symbol),
    )
    option_metrics[1].metric(
        "Theoretical premium / contract",
        _format_money(premium_per_contract, currency_symbol),
    )
    option_metrics[2].metric(
        "Intrinsic value / share",
        _format_money(intrinsic_value, currency_symbol),
    )
    option_metrics[3].metric(
        "Break-even at expiry",
        _format_money(breakeven, currency_symbol),
    )
    st.caption(
        f"Model value of the position: "
        f"{_format_money(position_sign * premium_per_contract * int(contract_count), currency_symbol)}. "
        f"Risk-free rate: {annual_risk_free_rate:.2%}; contract premium is theoretical, "
        "not a traded market quote."
    )

    greek_rows = [
        {
            "Greek": "Delta",
            "Position sensitivity": position_sign
            * contract_scale
            * valuation.delta,
            "Approximate change": "Currency per $1 underlying move",
        },
        {
            "Greek": "Gamma",
            "Position sensitivity": position_sign
            * contract_scale
            * valuation.gamma,
            "Approximate change": "Delta change per $1 underlying move",
        },
        {
            "Greek": "Vega",
            "Position sensitivity": position_sign
            * contract_scale
            * valuation.vega
            / 100.0,
            "Approximate change": "Currency per 1 volatility point",
        },
        {
            "Greek": "Theta",
            "Position sensitivity": position_sign
            * contract_scale
            * valuation.theta
            / 365.0,
            "Approximate change": "Currency per calendar day",
        },
        {
            "Greek": "Rho",
            "Position sensitivity": position_sign
            * contract_scale
            * valuation.rho
            / 100.0,
            "Approximate change": "Currency per 1 rate point",
        },
    ]
    st.markdown("#### Greeks for the selected position")
    st.dataframe(
        pd.DataFrame(greek_rows).style.format(
            {"Position sensitivity": lambda value: f"{value:,.4f}"}
        ),
        width="stretch",
        hide_index=True,
    )

    st.markdown("#### Spot and volatility scenarios")
    scenario_rows = []
    scenario_days = max(1, int(round(int(expiry_days) / 2)))
    for spot_shock in (-20, -10, 0, 10, 20):
        for volatility_shock in (-10, 0, 10):
            shocked_spot = max(0.01, option_spot * (1 + spot_shock / 100))
            shocked_volatility = max(
                0.001, volatility_percent / 100 + volatility_shock / 100
            )
            scenario_value = black_scholes(
                spot=shocked_spot,
                strike=option_strike,
                time_to_expiry_years=scenario_days / 365.0,
                volatility=shocked_volatility,
                risk_free_rate=annual_risk_free_rate,
                dividend_yield=dividend_yield_percent / 100.0,
                option_type=option_type,
            ).theoretical_price
            scenario_rows.append(
                {
                    "Spot shock": f"{spot_shock:+d}%",
                    "Volatility shock": f"{volatility_shock:+d} points",
                    "Scenario model premium / share": scenario_value,
                    "Position P&L vs current model": position_sign
                    * contract_scale
                    * (scenario_value - valuation.theoretical_price),
                }
            )
    st.caption(
        f"Scenarios use {scenario_days} calendar days remaining. "
        "P&L is mark-to-model versus today's theoretical premium."
    )
    st.dataframe(
        pd.DataFrame(scenario_rows).style.format(
            {
                "Scenario model premium / share": lambda value: _format_money(
                    value, currency_symbol
                ),
                "Position P&L vs current model": lambda value: _format_money(
                    value, currency_symbol
                ),
            }
        ),
        width="stretch",
        hide_index=True,
    )

    st.markdown("#### Time decay and expiry payoff")
    time_decay_days = sorted(
        {1}
        | {
            max(1, int(round(int(expiry_days) * fraction)))
            for fraction in (0.25, 0.5, 0.75, 1.0)
        }
    )
    time_decay = pd.DataFrame(
        [
            {
                "Days remaining": days,
                "Theoretical premium / share": black_scholes(
                    option_spot,
                    option_strike,
                    days / 365.0,
                    volatility_percent / 100.0,
                    annual_risk_free_rate,
                    dividend_yield_percent / 100.0,
                    option_type,
                ).theoretical_price,
            }
            for days in time_decay_days
        ]
    )
    st.line_chart(
        time_decay,
        x="Days remaining",
        y="Theoretical premium / share",
        width="stretch",
    )
    terminal_spots = [
        option_spot * (0.5 + index / 40.0) for index in range(41)
    ]
    expiry_payoff = pd.DataFrame(
        {
            "Underlying price at expiry": terminal_spots,
            "Expiry P&L vs model premium": [
                position_sign
                * contract_scale
                * (
                    (
                        max(terminal_spot - option_strike, 0.0)
                        if option_type == "call"
                        else max(option_strike - terminal_spot, 0.0)
                    )
                    - valuation.theoretical_price
                )
                for terminal_spot in terminal_spots
            ]
        }
    )
    st.line_chart(
        expiry_payoff,
        x="Underlying price at expiry",
        y="Expiry P&L vs model premium",
        width="stretch",
    )

with export_tab:
    st.subheader("Download your analysis")
    st.caption("Exports contain only your uploaded portfolio data and calculated metrics.")
    metrics_frame = _build_metrics_frame(risk, currency_choice)
    export_left, export_right = st.columns(2)
    with export_left:
        st.download_button(
            "Download holdings CSV",
            data=holdings.to_csv(index=False).encode("utf-8"),
            file_name="portfolio_holdings_analysis.csv",
            mime="text/csv",
            width="stretch",
        )
    with export_right:
        st.download_button(
            "Download risk metrics CSV",
            data=metrics_frame.to_csv(index=False).encode("utf-8"),
            file_name="portfolio_risk_metrics.csv",
            mime="text/csv",
            width="stretch",
        )
    st.markdown("#### Metrics included")
    st.dataframe(metrics_frame, width="stretch", hide_index=True)
    st.download_button(
        "Download indexed performance history",
        data=indexed_performance.to_csv(index_label="date").encode("utf-8"),
        file_name="portfolio_indexed_performance.csv",
        mime="text/csv",
    )

st.divider()
st.caption(
    "Fixed quantities; excludes fees, rebalancing and external cash flows. "
    "Historical estimates are not forecasts or investment advice. "
    "Returns exclude distributions unless adjusted_close was supplied."
)
