from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from portfolio_risk_analytics.portfolio_tracker import (
    calculate_risk_metrics,
    load_positions,
    load_price_history,
    summarize_portfolio,
)


st.set_page_config(page_title="Portfolio Risk Dashboard", page_icon="📉", layout="wide")

CSS = """
<style>
    .stApp {
        background: radial-gradient(circle at top left, #13243d 0%, #0b1220 42%, #090d16 100%);
        color: #edf4ff;
    }
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    .stMetric {
        background: rgba(17, 24, 39, 0.82);
        border: 1px solid rgba(126, 156, 255, 0.28);
        border-radius: 0.85rem;
        box-shadow: 0 18px 35px rgba(0,0,0,0.2);
        padding: 0.9rem 1rem;
    }
    .stMetric [data-testid="stMetricValue"] {
        color: #f5f9ff;
        font-weight: 700;
        font-size: 1.6rem;
    }
    .stTabs [role="tablist"] {
        gap: 0.5rem;
    }
    .stTabs [role="tab"] {
        background: rgba(255,255,255,0.05);
        border-radius: 0.7rem 0.7rem 0 0;
        color: #dfeaff;
        border: 1px solid rgba(255,255,255,0.08);
    }
    .stTabs [role="tab"][aria-selected="true"] {
        background: linear-gradient(180deg, #3a70ff 0%, #2a57c8 100%);
        color: white;
        border-color: rgba(255,255,255,0.16);
    }
    .stDataFrame {
        background: rgba(255,255,255,0.02);
        border-radius: 0.75rem;
    }
    h1, h2, h3 {
        color: #f5f8ff;
    }
    p, div, label {
        color: #e5edff;
    }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


def _as_temp_file(uploaded_file) -> Path:
    if uploaded_file is None:
        raise ValueError("No file uploaded.")
    suffix = Path(uploaded_file.name).suffix or ".csv"
    with tempfile.NamedTemporaryFile("wb", suffix=suffix, delete=False) as tmp:
        tmp.write(uploaded_file.getvalue())
        return Path(tmp.name)


def _format_money(value: float | int) -> str:
    return f"€{float(value):,.2f}"


st.title("Portfolio Risk Analytics")
st.caption("Performance • Risk • Allocation")

with st.sidebar:
    st.header("Data inputs")
    st.file_uploader(
        "Portfolio CSV",
        type=["csv"],
        help="Required columns: symbol, quantity, purchase_price, current_price",
        key="portfolio_upload",
    )
    st.file_uploader(
        "Price history CSV",
        type=["csv"],
        help="Required columns: date, symbol1, symbol2, ...",
        key="prices_upload",
    )
    st.markdown("---")
    st.caption("Default sample data is loaded automatically when no file is uploaded.")

base_dir = Path(__file__).resolve().parent
sample_positions = base_dir / "sample_portfolio.csv"
sample_prices = base_dir / "sample_prices.csv"

portfolio_upload = st.session_state.get("portfolio_upload")
prices_upload = st.session_state.get("prices_upload")

positions_path = _as_temp_file(portfolio_upload) if portfolio_upload is not None else sample_positions
prices_path = _as_temp_file(prices_upload) if prices_upload is not None else sample_prices

try:
    positions = load_positions(positions_path)
    summary = summarize_portfolio(positions)
    history = None
    risk = None

    if prices_path.exists():
        history = load_price_history(prices_path, (position.symbol for position in positions))
        risk = calculate_risk_metrics(positions, history, annual_risk_free_rate=0.03)

    holdings = pd.DataFrame(
        [
            {
                "Symbol": p.symbol,
                "Quantity": float(p.quantity),
                "Purchase price": float(p.purchase_price),
                "Current price": float(p.current_price),
                "Market value": float(p.market_value),
                "Unrealized P&L": float(p.unrealized_pnl),
                "Return": float(p.return_rate),
                "Weight": float(p.market_value / summary.total_market_value),
            }
            for p in summary.positions
        ]
    )

    metric_cols = st.columns(4)
    metric_cols[0].metric("Portfolio value", _format_money(summary.total_market_value))
    metric_cols[1].metric("Cost basis", _format_money(summary.total_cost_basis))
    metric_cols[2].metric("Unrealized P&L", _format_money(summary.total_unrealized_pnl))
    metric_cols[3].metric("Total return", f"{summary.total_return_rate:.2%}")

    tab_overview, tab_risk, tab_holdings = st.tabs(["Overview", "Risk", "Holdings"])

    with tab_overview:
        st.subheader("Portfolio evolution")
        if history is not None:
            price_df = pd.DataFrame(
                [
                    {
                        "Date": observation.observation_date.isoformat(),
                        **{symbol: float(value) for symbol, value in observation.closing_prices.items()},
                    }
                    for observation in history
                ]
            ).set_index("Date")
            st.line_chart(price_df)
        else:
            st.info("Add a historical price CSV to plot performance by date.")

        st.subheader("Allocation by holding")
        st.bar_chart(holdings.set_index("Symbol")["Weight"] * 100)

    with tab_risk:
        if risk is not None:
            risk_cols = st.columns(4)
            risk_cols[0].metric("Cumulative return", f"{risk.cumulative_return:.2%}")
            risk_cols[1].metric("Annualized volatility", f"{risk.annualized_volatility:.2%}")
            risk_cols[2].metric("Sharpe ratio", "N/A" if risk.sharpe_ratio is None else f"{risk.sharpe_ratio:.2f}")
            risk_cols[3].metric("Max drawdown", f"{risk.max_drawdown:.2%}")

            st.write(
                f"Historical 95% VaR (daily): {risk.historical_var_95:.2%} | "
                f"Expected shortfall: {risk.expected_shortfall_95:.2%}"
            )

            if risk.risk_contribution_pct:
                st.subheader("Euler risk contribution by holding")
                contribution_df = pd.DataFrame(
                    [
                        {
                            "Symbol": symbol,
                            "Annualized volatility": risk.asset_volatility[symbol],
                            "Risk contribution": contribution,
                        }
                        for symbol, contribution in risk.risk_contribution_pct.items()
                    ]
                ).set_index("Symbol")
                st.dataframe(
                    contribution_df.style.format(
                        {
                            "Annualized volatility": "{:.2%}".format,
                            "Risk contribution": "{:.2%}".format,
                        }
                    ),
                    use_container_width=True,
                )
                st.caption(
                    "Contributions use latest portfolio weights and annualized sample covariance; "
                    "negative contributions indicate a hedge effect."
                )

            if risk.correlation_matrix:
                st.subheader("Historical asset correlation")
                correlation_df = pd.DataFrame.from_dict(
                    risk.correlation_matrix, orient="index"
                )
                st.dataframe(
                    correlation_df.style.format("{:.2f}").background_gradient(
                        cmap="RdYlGn", vmin=-1, vmax=1
                    ),
                    use_container_width=True,
                )
        else:
            st.info("Upload a historical price CSV to compute risk metrics.")

    with tab_holdings:
        st.dataframe(
            holdings[
                [
                    "Symbol",
                    "Quantity",
                    "Purchase price",
                    "Current price",
                    "Market value",
                    "Unrealized P&L",
                    "Return",
                    "Weight",
                ]
            ].style.format(
                {
                    "Purchase price": "€{:.2f}".format,
                    "Current price": "€{:.2f}".format,
                    "Market value": "€{:.2f}".format,
                    "Unrealized P&L": "€{:.2f}".format,
                    "Return": "{:.2%}".format,
                    "Weight": "{:.2%}".format,
                }
            ),
            use_container_width=True,
        )

except Exception as exc:
    st.error(f"Unable to load portfolio data: {exc}")
    st.stop()
