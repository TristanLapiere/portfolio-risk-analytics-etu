"""On-demand historical prices from Yahoo Finance's unofficial chart endpoint."""

from __future__ import annotations

import csv
import json
import math
from datetime import date, datetime, time, timedelta, timezone
from io import StringIO
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


def fetch_yahoo_price_csv(
    symbols: list[str],
    quantities: list[float],
    start_date: date,
    end_date: date,
) -> str:
    """Fetch common daily observations with both raw and adjusted closes."""
    normalized_symbols = [symbol.strip().upper() for symbol in symbols]
    if (
        not normalized_symbols
        or any(not symbol for symbol in normalized_symbols)
        or len(set(normalized_symbols)) != len(normalized_symbols)
    ):
        raise ValueError("Enter one or more distinct, non-empty ticker symbols.")
    if len(quantities) != len(normalized_symbols):
        raise ValueError("Enter exactly one quantity for each ticker symbol.")
    if any(not math.isfinite(quantity) or quantity <= 0 for quantity in quantities):
        raise ValueError("Every quantity must be a finite number greater than zero.")
    if end_date < start_date:
        raise ValueError("The end date must be on or after the start date.")

    start_timestamp = int(
        datetime.combine(start_date, time.min, timezone.utc).timestamp()
    )
    end_timestamp = int(
        datetime.combine(end_date + timedelta(days=1), time.min, timezone.utc).timestamp()
    )
    histories: dict[str, dict[date, tuple[float, float]]] = {}
    for symbol in normalized_symbols:
        query = urlencode(
            {
                "period1": start_timestamp,
                "period2": end_timestamp,
                "interval": "1d",
                "events": "div,splits",
            }
        )
        request = Request(
            "https://query1.finance.yahoo.com/v8/finance/chart/"
            f"{quote(symbol, safe='')}?{query}",
            headers={"User-Agent": "Mozilla/5.0"},
        )
        try:
            with urlopen(request, timeout=30) as response:
                payload = json.load(response)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            raise RuntimeError(
                f"Could not download historical prices for {symbol}: {error}"
            ) from error

        chart = payload.get("chart", {})
        if chart.get("error") or not chart.get("result"):
            raise RuntimeError(
                f"Yahoo Finance returned no price history for {symbol}: "
                f"{chart.get('error')}"
            )
        result = chart["result"][0]
        timestamps = result.get("timestamp", [])
        indicators = result.get("indicators", {})
        closes = indicators.get("quote", [{}])[0].get("close", [])
        adjusted_closes = indicators.get("adjclose", [{}])[0].get("adjclose", [])
        if not adjusted_closes:
            raise RuntimeError(
                f"Yahoo Finance did not return adjusted closing prices for {symbol}."
            )

        prices: dict[date, tuple[float, float]] = {}
        for timestamp, close, adjusted_close in zip(
            timestamps, closes, adjusted_closes
        ):
            observation_date = datetime.fromtimestamp(
                timestamp, timezone.utc
            ).date()
            if not start_date <= observation_date <= end_date:
                continue
            if close is None or adjusted_close is None:
                continue
            raw_price = float(close)
            total_return_price = float(adjusted_close)
            if (
                math.isfinite(raw_price)
                and raw_price > 0
                and math.isfinite(total_return_price)
                and total_return_price > 0
            ):
                prices[observation_date] = (raw_price, total_return_price)
        if not prices:
            raise RuntimeError(
                f"No valid daily prices were returned for {symbol} in the selected period."
            )
        histories[symbol] = prices

    common_dates = sorted(
        set.intersection(*(set(history) for history in histories.values()))
    )
    if len(common_dates) < 3:
        raise RuntimeError(
            "Yahoo Finance returned fewer than three common daily observations "
            "for the selected symbols and period."
        )

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["date", "symbol", "close", "adjusted_close", "quantity"])
    quantity_by_symbol = dict(zip(normalized_symbols, quantities))
    for observation_date in common_dates:
        for symbol in normalized_symbols:
            close, adjusted_close = histories[symbol][observation_date]
            writer.writerow(
                [
                    observation_date.isoformat(),
                    symbol,
                    f"{close:.8f}",
                    f"{adjusted_close:.8f}",
                    f"{quantity_by_symbol[symbol]:.8f}",
                ]
            )
    return output.getvalue()
