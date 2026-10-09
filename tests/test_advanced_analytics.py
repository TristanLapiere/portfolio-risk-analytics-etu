import json
import math
import unittest
from datetime import date
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from portfolio_risk_analytics.market_data import fetch_yahoo_price_csv
from portfolio_risk_analytics.options_analytics import black_scholes
from portfolio_risk_analytics.portfolio_tracker import (
    calculate_risk_metrics,
    load_portfolio_data,
    portfolio_total_return_values,
)


class BlackScholesTests(unittest.TestCase):
    def test_known_atm_call_and_put_prices(self) -> None:
        call = black_scholes(100, 100, 1, 0.2, 0.05, option_type="call")
        put = black_scholes(100, 100, 1, 0.2, 0.05, option_type="put")

        self.assertAlmostEqual(call.theoretical_price, 10.4506, places=4)
        self.assertAlmostEqual(put.theoretical_price, 5.5735, places=4)
        self.assertGreater(call.delta, 0)
        self.assertLess(put.delta, 0)
        self.assertGreater(call.gamma, 0)
        self.assertGreater(call.vega, 0)
        self.assertLess(call.theta, 0)
        self.assertGreater(call.rho, 0)
        self.assertLess(put.rho, 0)

    def test_put_call_parity_with_continuous_dividend_yield(self) -> None:
        spot, strike, years, rate, dividend_yield = 100, 95, 0.75, 0.04, 0.015
        call = black_scholes(
            spot, strike, years, 0.3, rate, dividend_yield, "call"
        )
        put = black_scholes(
            spot, strike, years, 0.3, rate, dividend_yield, "put"
        )
        expected = (
            spot * math.exp(-dividend_yield * years)
            - strike * math.exp(-rate * years)
        )

        self.assertAlmostEqual(call.theoretical_price - put.theoretical_price, expected)

    def test_rejects_invalid_option_inputs(self) -> None:
        with self.assertRaisesRegex(ValueError, "Volatility"):
            black_scholes(100, 100, 1, 0, 0.03)
        with self.assertRaisesRegex(ValueError, "Option type"):
            black_scholes(100, 100, 1, 0.2, 0.03, option_type="binary")


class AdjustedPriceTests(unittest.TestCase):
    def test_adjusted_returns_change_performance_but_keep_raw_market_value(self) -> None:
        csv_text = StringIO(
            "date,symbol,close,adjusted_close,quantity\n"
            "2025-01-01,AAA,100,100,1\n"
            "2025-01-02,AAA,99,101,1\n"
            "2025-01-03,AAA,98,102,1\n"
        )

        positions, history = load_portfolio_data(csv_text)
        metrics = calculate_risk_metrics(positions, history)

        self.assertEqual(positions[0].current_price, Decimal("98"))
        self.assertAlmostEqual(metrics.cumulative_return, 0.02)
        self.assertAlmostEqual(
            portfolio_total_return_values(positions, history)[-1], 102
        )

    def test_missing_adjusted_price_is_reported(self) -> None:
        csv_text = StringIO(
            "date,symbol,close,adjusted_close,quantity\n"
            "2025-01-01,AAA,100,100,1\n"
            "2025-01-02,AAA,99,,1\n"
            "2025-01-03,AAA,98,102,1\n"
        )

        with self.assertRaisesRegex(ValueError, "adjusted_close"):
            load_portfolio_data(csv_text)

    def test_adjusted_portfolio_return_keeps_fixed_quantities(self) -> None:
        csv_text = StringIO(
            "date,symbol,close,adjusted_close,quantity\n"
            "2025-01-01,AAA,100,100,1\n"
            "2025-01-01,BBB,100,100,1\n"
            "2025-01-02,AAA,110,110,1\n"
            "2025-01-02,BBB,90,100,1\n"
            "2025-01-03,AAA,121,121,1\n"
            "2025-01-03,BBB,81,100,1\n"
        )

        positions, history = load_portfolio_data(csv_text)

        self.assertEqual(
            portfolio_total_return_values(positions, history), [200, 210, 221]
        )


class YahooMarketDataTests(unittest.TestCase):
    def test_download_formats_raw_and_adjusted_prices(self) -> None:
        payload = {
            "chart": {
                "result": [
                    {
                        "timestamp": [
                            1735689600,
                            1735776000,
                            1735862400,
                        ],
                        "indicators": {
                            "quote": [{"close": [100.0, 99.0, 98.0]}],
                            "adjclose": [{"adjclose": [100.0, 101.0, 102.0]}],
                        },
                    }
                ],
                "error": None,
            }
        }

        with patch("portfolio_risk_analytics.market_data.urlopen") as open_url:
            open_url.return_value.__enter__.return_value = StringIO(
                json.dumps(payload)
            )
            csv_text = fetch_yahoo_price_csv(
                ["AAA"], [2.0], date(2025, 1, 1), date(2025, 1, 3)
            )

        self.assertIn("date,symbol,close,adjusted_close,quantity", csv_text)
        positions, history = load_portfolio_data(StringIO(csv_text))
        self.assertEqual(positions[0].quantity, 2)
        self.assertEqual(positions[0].current_price, Decimal("98"))
        self.assertAlmostEqual(
            float(history[-1].adjusted_closing_prices["AAA"]), 102
        )

    def test_rejects_quantity_count_mismatch_before_request(self) -> None:
        with patch("portfolio_risk_analytics.market_data.urlopen") as open_url:
            with self.assertRaisesRegex(ValueError, "exactly one quantity"):
                fetch_yahoo_price_csv(
                    ["AAA", "BBB"], [1], date(2025, 1, 1), date(2025, 1, 3)
                )
        open_url.assert_not_called()


if __name__ == "__main__":
    unittest.main()
