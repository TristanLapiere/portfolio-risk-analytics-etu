"""Download daily raw and distribution-adjusted closes from Yahoo Finance."""

from __future__ import annotations

import csv
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


START_DATE = date(2020, 1, 1)
ASSET_QUANTITIES = {
    "SPY": 20,  # S&P 500 equities
    "QQQ": 20,  # Nasdaq-100 equities
    "IWM": 20,  # US small-cap equities
    "TLT": 30,  # US long-duration Treasury bonds
    "GLD": 20,  # Gold
}
OUTPUT_FILE = Path(__file__).resolve().parent / "real_market_case.csv"


def fetch_market_closes(
    symbol: str, end_date: date
) -> dict[date, tuple[float, float]]:
    parameters = urlencode(
        {
            "period1": int(
                datetime.combine(START_DATE, datetime.min.time(), timezone.utc).timestamp()
            ),
            "period2": int(
                datetime.combine(end_date, datetime.min.time(), timezone.utc).timestamp()
            ),
            "interval": "1d",
            "events": "div,splits",
        }
    )
    request = Request(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?{parameters}",
        headers={"User-Agent": "Mozilla/5.0"},
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except (HTTPError, URLError, TimeoutError) as error:
        raise RuntimeError(f"Could not download {symbol} historical prices: {error}") from error

    chart = payload.get("chart", {})
    if chart.get("error") or not chart.get("result"):
        raise RuntimeError(
            f"Yahoo Finance returned no price history for {symbol}: {chart.get('error')}"
        )

    result = chart["result"][0]
    timestamps = result.get("timestamp", [])
    closes = result.get("indicators", {}).get("quote", [{}])[0].get("close", [])
    adjusted_closes = (
        result.get("indicators", {}).get("adjclose", [{}])[0].get("adjclose", [])
    )
    prices = {}
    for timestamp, close, adjusted_close in zip(
        timestamps, closes, adjusted_closes
    ):
        if (
            close is not None
            and close > 0
            and adjusted_close is not None
            and adjusted_close > 0
        ):
            prices[datetime.fromtimestamp(timestamp, timezone.utc).date()] = (
                float(close),
                float(adjusted_close),
            )
    if not prices:
        raise RuntimeError(f"No valid daily closing prices were returned for {symbol}.")
    return prices


def main() -> None:
    end_date = date.today() + timedelta(days=1)
    histories = {
        symbol: fetch_market_closes(symbol, end_date)
        for symbol in ASSET_QUANTITIES
    }
    common_dates = sorted(set.intersection(*(set(prices) for prices in histories.values())))
    if len(common_dates) < 60:
        raise RuntimeError(
            f"Only {len(common_dates)} common observations downloaded; refusing "
            "to produce a short or incomplete test dataset."
        )

    with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["date", "symbol", "close", "adjusted_close", "quantity"])
        for observation_date in common_dates:
            for symbol, quantity in ASSET_QUANTITIES.items():
                close, adjusted_close = histories[symbol][observation_date]
                writer.writerow(
                    [
                        observation_date.isoformat(),
                        symbol,
                        f"{close:.6f}",
                        f"{adjusted_close:.6f}",
                        quantity,
                    ]
                )

    print(f"Wrote {len(common_dates)} common daily observations to {OUTPUT_FILE}")
    print(
        "Symbols: "
        + ", ".join(ASSET_QUANTITIES)
        + f" | period: {common_dates[0]} to {common_dates[-1]}"
    )


if __name__ == "__main__":
    main()
