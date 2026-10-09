# Portfolio Risk Analytics

Interactive Streamlit dashboard for multi-asset portfolio performance,
historical risk analysis and European option sensitivities. The dashboard
starts with no portfolio loaded: upload a CSV, select the optional local
market case, or fetch daily prices from Yahoo Finance. `examples/sample_prices.csv`
is a fictional example you can upload or download from the app. Details on the
optional real-market case are in [examples/REAL_MARKET_CASE.md](examples/REAL_MARKET_CASE.md).
The downloaded Yahoo Finance snapshot is intentionally excluded from this
public repository; generate it locally with `python examples/fetch_real_market_data.py`
after reviewing the provider's terms. Once generated, it can be selected in
the dashboard.

For a detailed French explanation of the purpose, formulas, interpretation, and
limitations of every displayed metric, see the rendered
[PDF guide](docs/GUIDE_METHODOLOGIQUE_FR.pdf) or the
[HTML guide](docs/GUIDE_METHODOLOGIQUE_FR.html). The editable Markdown source is
[GUIDE_METHODOLOGIQUE_FR.md](docs/GUIDE_METHODOLOGIQUE_FR.md).
To regenerate the PDF and HTML (with rendered equations), run
`Rscript docs/render_guide.R` from the project root.

## Project layout

```text
.
├── app/                         # Streamlit entry point
├── src/portfolio_risk_analytics/ # Reusable analytics package
├── tests/                       # Unit tests
├── examples/                    # Sample input and data utilities
├── docs/                        # Methodology guide and rendered versions
├── archive/                     # Historical dashboard version
├── .github/workflows/           # Continuous integration
├── pyproject.toml               # Package metadata and dependencies
└── requirements.txt             # Editable project install
```

The package separates portfolio calculations, options analytics and market
data retrieval. `examples/real_market_case.csv` is generated locally and is not
tracked in this public repository.

## One-file input format

The CSV must contain one row per asset per date, with these columns:

| Column | Meaning |
| --- | --- |
| `date` | Observation date in `YYYY-MM-DD` format |
| `symbol` | Asset identifier |
| `close` | Positive closing price |
| `adjusted_close` | Optional dividend- and split-adjusted close for total-return analysis |
| `quantity` | Positive held quantity; constant for that symbol in the file |

Example:

```csv
date,symbol,close,quantity
2025-01-02,ALFA,100,10
2025-01-02,BETA,250,4
2025-01-03,ALFA,103,10
2025-01-03,BETA,248,4
2025-01-06,ALFA,101,10
2025-01-06,BETA,252,4
```

At least three distinct dates are required for sample-covariance estimates.
Each date must contain a price for every symbol. Rows may be in any order;
dates are sorted when loaded. The app reports input errors rather than silently
dropping invalid or incomplete observations. Comma-delimited CSV with decimal
points and French semicolon-delimited CSV with decimal commas are both accepted.

## Quantitative methods

- Close-to-close simple returns and fixed-quantity portfolio valuation
- Annualized sample volatility, Sharpe ratio and Sortino ratio (252 trading days)
- Historical and Gaussian parametric one-day VaR and expected shortfall (90%, 95% or 99%)
- EWMA annualized volatility (`lambda = 0.94`)
- Maximum drawdown, Calmar ratio, rolling 21-observation volatility
- Sample covariance and correlation matrices
- Euler volatility contribution by asset using latest market-value weights

Historical and Gaussian tail estimates are model-dependent and become more
informative with longer histories. The parametric VaR/ES assumes normally
distributed returns. Position quantities are fixed for market-value calculations;
the model excludes rebalancing, transaction costs, taxes and external cash flows.
Dividend treatment depends on whether adjusted closes are supplied. Metrics are
descriptive historical estimates, not forecasts or investment advice.

When `adjusted_close` is present, risk/performance returns use adjusted closes
while holdings and option spot defaults use raw `close`. Otherwise, returns use
raw closes and exclude distributions. The Yahoo Finance importer is on-demand,
requires no API key, and downloads both fields. Yahoo's chart endpoint is
unofficial, may be throttled or changed, and must not be treated as a live quote
feed; review Yahoo's terms before redistributing data.

The dashboard also includes parallel/custom instantaneous price-shock scenarios,
a display-currency label selector (no foreign-exchange conversion), and CSV
exports for holdings, performance history and risk metrics.

## Options analytics

The Options tab prices one European call or put with Black–Scholes using the
selected underlying's latest raw close (editable), strike, expiry, volatility,
risk-free rate, and continuous dividend yield. It reports a theoretical premium,
position Greeks (Delta, Gamma, Vega, Theta and Rho), expiry payoff/break-even,
and spot/volatility/time-decay scenarios. Volatility defaults to the historical
realized estimate and can be edited; it is not implied volatility. The default
contract multiplier is 100 shares and can be changed.

This is a model simulator, not a live options chain: premiums are not market
quotes, and the model assumes European exercise, constant volatility/rates/yield,
continuous trading and no transaction costs. It is educational, not investment
advice.

## Run the dashboard

From this directory:

```bash
python3 -m pip install -r requirements.txt
python3 -m streamlit run app/streamlit_app.py
```

Open http://localhost:8501 and upload your CSV, choose the local real-market
case if generated, or fetch an adjusted history from Yahoo Finance.

## Run the command-line analysis

```bash
python3 -m portfolio_risk_analytics.portfolio_tracker examples/sample_prices.csv --risk-free-rate 0.03
```

## Run the tests

```bash
python3 -m unittest discover -s tests -v
```

The synthetic example prices and assets are fictional.
