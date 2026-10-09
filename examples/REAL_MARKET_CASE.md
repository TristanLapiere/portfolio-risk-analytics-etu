# Real-market stress-test dataset

`real_market_case.csv` is a locally generated, long-format daily
historical-price case for five US-listed exchange-traded funds. It is ignored
by Git and is not included in the public repository:

| Ticker | Exposure | Constant quantity |
| --- | --- | ---: |
| SPY | S&P 500 large-cap US equities | 20 |
| QQQ | Nasdaq-100 equities | 20 |
| IWM | Russell 2000 US small-cap equities | 20 |
| TLT | US Treasury bonds with long maturities | 30 |
| GLD | Gold | 20 |

## Data provenance

- Provider: Yahoo Finance historical chart data.
- Source endpoint: `https://query1.finance.yahoo.com/v8/finance/chart/{ticker}`
- Source series: daily `close` and `adjclose` fields returned by the chart
  endpoint. `close` is the raw market close used for market value and option spot;
  `adjusted_close` is adjusted for distributions and splits and is used for
  historical performance and risk returns.
- Currency: USD.
- Requested start: 2020-01-01; the first available common market observation is
  2020-01-02.
- Last downloaded observation: 2026-10-08.
- All five funds have 1,701 common daily observations in this snapshot.
- `fetch_real_market_data.py` downloads a fresh snapshot using the same public
  endpoint and rewrites `real_market_case.csv`. A later download will naturally
  have a different last date and can have revised historical values.

The selected assets provide genuinely different market exposures: US large
caps, technology-heavy equities, small caps, long-duration Treasury bonds and
gold. The period contains the February–March 2020 COVID equity shock, the
2022 equity/bond sell-off during rapid rate increases, and subsequent market
regimes. It is a useful exercise for observing changing correlations,
diversification, drawdowns, tail estimates and stress scenarios—not an optimized
or recommended investment portfolio.

## How to run it

From the project directory:

```bash
python3 -m streamlit run streamlit_app.py
```

The dashboard's **Included real-market case** choice appears after you generate
the CSV locally. Alternatively, import the CSV directly, or use the Yahoo
Finance on-demand form.

To refresh the downloadable data:

```bash
python3 examples/fetch_real_market_data.py
```

## Interpretation and restrictions

This is historical market data for demonstration and education. Adjusted-close
returns approximate a total return with distributions reinvested; the file does
not contain individual dividend cash flows. It excludes transaction costs,
taxes, FX translation, rebalancing and external cash flows. The quantities are
fixed and deliberately chosen as a plausible test portfolio, not as investment
advice. Yahoo Finance's chart endpoint is unofficial and may change or throttle
access; verify current terms before redistributing or using the data commercially.
See [Yahoo Finance terms of service](https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html).
The public source repository intentionally excludes this downloaded price file
to avoid redistributing third-party market data without confirmed permission.
