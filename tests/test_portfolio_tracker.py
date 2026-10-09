import csv
import io
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from portfolio_risk_analytics.portfolio_tracker import (
    Position,
    PriceObservation,
    calculate_risk_metrics,
    format_report,
    load_portfolio_data,
    load_positions,
    load_price_history,
    summarize_portfolio,
)


class PortfolioTrackerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.positions = [
            Position("AAA", Decimal("1"), Decimal("100"), Decimal("108.9"))
        ]
        self.history = [
            PriceObservation(date(2025, 1, 1), {"AAA": Decimal("100")}),
            PriceObservation(date(2025, 1, 2), {"AAA": Decimal("110")}),
            PriceObservation(date(2025, 1, 3), {"AAA": Decimal("99")}),
            PriceObservation(date(2025, 1, 4), {"AAA": Decimal("108.9")}),
        ]

    def test_summary_calculates_value_pnl_and_weighted_return(self) -> None:
        summary = summarize_portfolio(
            [
                Position("AAA", Decimal("10"), Decimal("100"), Decimal("110")),
                Position("BBB", Decimal("5"), Decimal("200"), Decimal("180")),
            ]
        )

        self.assertEqual(summary.total_cost_basis, Decimal("2000"))
        self.assertEqual(summary.total_market_value, Decimal("2000"))
        self.assertEqual(summary.total_unrealized_pnl, Decimal("0"))
        self.assertEqual(summary.total_return_rate, Decimal("0"))
        self.assertEqual(summary.positions[0].unrealized_pnl, Decimal("100"))
        self.assertEqual(summary.positions[1].unrealized_pnl, Decimal("-100"))

    def test_loads_positions_csv(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            csv_path = Path(directory) / "positions.csv"
            with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
                writer = csv.DictWriter(
                    csv_file,
                    fieldnames=[
                        "symbol",
                        "quantity",
                        "purchase_price",
                        "current_price",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "symbol": "AAA",
                        "quantity": "2",
                        "purchase_price": "50",
                        "current_price": "55",
                    }
                )

            positions = load_positions(csv_path)

        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0].symbol, "AAA")
        self.assertEqual(positions[0].market_value, Decimal("110"))

    def test_loads_dated_price_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            csv_path = Path(directory) / "prices.csv"
            csv_path.write_text(
                "date,AAA\n2025-01-01,100\n2025-01-02,110\n",
                encoding="utf-8",
            )

            history = load_price_history(csv_path, ["AAA"])

        self.assertEqual(len(history), 2)
        self.assertEqual(history[1].closing_prices["AAA"], Decimal("110"))

    def test_loads_positions_and_history_from_one_csv(self) -> None:
        csv_data = io.StringIO(
            "date,symbol,close,quantity\n"
            "2025-01-03,AAA,110,2\n"
            "2025-01-01,AAA,100,2\n"
            "2025-01-02,AAA,105,2\n"
            "2025-01-01,BBB,50,1\n"
            "2025-01-02,BBB,55,1\n"
            "2025-01-03,BBB,52,1\n"
        )

        positions, history = load_portfolio_data(csv_data)

        self.assertEqual([row.observation_date for row in history], [
            date(2025, 1, 1), date(2025, 1, 2), date(2025, 1, 3)
        ])
        self.assertEqual([position.symbol for position in positions], ["AAA", "BBB"])
        self.assertEqual(positions[0].quantity, Decimal("2"))
        self.assertEqual(positions[0].purchase_price, Decimal("100"))
        self.assertEqual(positions[0].current_price, Decimal("110"))

    def test_loads_french_semicolon_csv_with_decimal_commas(self) -> None:
        csv_data = io.StringIO(
            "date;symbol;close;quantity\n"
            "2025-01-01;AAA;100,50;1,5\n"
            "2025-01-02;AAA;101,25;1,5\n"
            "2025-01-03;AAA;102,00;1,5\n"
        )

        positions, history = load_portfolio_data(csv_data)

        self.assertEqual(positions[0].quantity, Decimal("1.5"))
        self.assertEqual(positions[0].purchase_price, Decimal("100.50"))
        self.assertEqual(history[-1].closing_prices["AAA"], Decimal("102.00"))

    @unittest.skipUnless(
        (Path(__file__).resolve().parents[1] / "examples" / "real_market_case.csv").is_file(),
        "Optional Yahoo Finance dataset is not included in the public source.",
    )
    def test_real_market_stress_case_loads_and_calculates(self) -> None:
        real_case = (
            Path(__file__).resolve().parents[1]
            / "examples"
            / "real_market_case.csv"
        )
        positions, history = load_portfolio_data(real_case)

        self.assertEqual(
            {position.symbol for position in positions},
            {"SPY", "QQQ", "IWM", "TLT", "GLD"},
        )
        self.assertGreaterEqual(len(history), 1500)
        self.assertEqual(history[0].observation_date, date(2020, 1, 2))
        self.assertIsNotNone(history[0].adjusted_closing_prices)
        self.assertIn(date(2020, 3, 23), {item.observation_date for item in history})

        metrics = calculate_risk_metrics(
            positions, history, annual_risk_free_rate=0.03, confidence_level=0.99
        )
        self.assertGreater(metrics.annualized_volatility, 0)
        self.assertLess(metrics.max_drawdown, 0)
        self.assertAlmostEqual(sum(metrics.risk_contribution_pct.values()), 1.0)

    def test_one_csv_rejects_inconsistent_quantities(self) -> None:
        csv_data = io.StringIO(
            "date,symbol,close,quantity\n"
            "2025-01-01,AAA,100,1\n"
            "2025-01-02,AAA,105,2\n"
            "2025-01-03,AAA,110,1\n"
        )

        with self.assertRaisesRegex(ValueError, "quantity for AAA must be constant"):
            load_portfolio_data(csv_data)

    def test_one_csv_rejects_missing_asset_price_on_a_date(self) -> None:
        csv_data = io.StringIO(
            "date,symbol,close,quantity\n"
            "2025-01-01,AAA,100,1\n"
            "2025-01-01,BBB,50,1\n"
            "2025-01-02,AAA,105,1\n"
            "2025-01-03,AAA,110,1\n"
            "2025-01-03,BBB,55,1\n"
        )

        with self.assertRaisesRegex(ValueError, "missing price.*BBB"):
            load_portfolio_data(csv_data)

    def test_rejects_non_increasing_price_dates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            csv_path = Path(directory) / "prices.csv"
            csv_path.write_text(
                "date,AAA\n2025-01-02,100\n2025-01-01,110\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "strictly increasing"):
                load_price_history(csv_path, ["AAA"])

    def test_historical_risk_metrics(self) -> None:
        metrics = calculate_risk_metrics(self.positions, self.history, 0.03)

        self.assertAlmostEqual(metrics.cumulative_return, 0.089)
        self.assertAlmostEqual(metrics.historical_var, 0.08)
        self.assertAlmostEqual(metrics.expected_shortfall, 0.10)
        self.assertAlmostEqual(metrics.max_drawdown, -0.10)
        self.assertGreater(metrics.annualized_volatility, 0)
        self.assertIsNotNone(metrics.sharpe_ratio)
        self.assertIsNotNone(metrics.sortino_ratio)
        self.assertIsNotNone(metrics.calmar_ratio)
        self.assertGreater(metrics.ewma_volatility, 0)
        self.assertGreater(metrics.parametric_var, metrics.historical_var)
        self.assertGreater(
            metrics.parametric_expected_shortfall, metrics.parametric_var
        )

    def test_asset_correlations_and_euler_risk_contributions(self) -> None:
        positions = [
            Position("AAA", Decimal("1"), Decimal("100"), Decimal("108.9")),
            Position("BBB", Decimal("2"), Decimal("50"), Decimal("54.45")),
        ]
        history = [
            PriceObservation(date(2025, 1, 1), {"AAA": Decimal("100"), "BBB": Decimal("50")}),
            PriceObservation(date(2025, 1, 2), {"AAA": Decimal("110"), "BBB": Decimal("55")}),
            PriceObservation(date(2025, 1, 3), {"AAA": Decimal("99"), "BBB": Decimal("49.5")}),
            PriceObservation(date(2025, 1, 4), {"AAA": Decimal("108.9"), "BBB": Decimal("54.45")}),
        ]

        metrics = calculate_risk_metrics(positions, history)

        self.assertAlmostEqual(metrics.correlation_matrix["AAA"]["BBB"], 1.0)
        self.assertAlmostEqual(sum(metrics.risk_contribution_pct.values()), 1.0)
        self.assertAlmostEqual(metrics.risk_contribution_pct["AAA"], 0.5)
        self.assertAlmostEqual(metrics.risk_contribution_pct["BBB"], 0.5)
        self.assertGreater(metrics.asset_volatility["AAA"], 0)

    def test_sharpe_ratio_is_unavailable_for_constant_prices(self) -> None:
        constant_history = [
            PriceObservation(date(2025, 1, 1), {"AAA": Decimal("100")}),
            PriceObservation(date(2025, 1, 2), {"AAA": Decimal("100")}),
        ]

        metrics = calculate_risk_metrics(self.positions, constant_history)

        self.assertEqual(metrics.annualized_volatility, 0)
        self.assertIsNone(metrics.sharpe_ratio)

    def test_confidence_level_changes_tail_risk_estimates(self) -> None:
        risk_90 = calculate_risk_metrics(
            self.positions, self.history, confidence_level=0.90
        )
        risk_99 = calculate_risk_metrics(
            self.positions, self.history, confidence_level=0.99
        )

        self.assertEqual(risk_90.confidence_level, 0.90)
        self.assertEqual(risk_99.confidence_level, 0.99)
        self.assertGreaterEqual(risk_99.historical_var, risk_90.historical_var)
        self.assertGreater(risk_99.parametric_var, risk_90.parametric_var)

    def test_rejects_invalid_confidence_level(self) -> None:
        with self.assertRaisesRegex(ValueError, "strictly between 0 and 1"):
            calculate_risk_metrics(self.positions, self.history, confidence_level=1.0)

    def test_rejects_missing_symbol_in_price_history(self) -> None:
        incomplete_history = [
            PriceObservation(date(2025, 1, 1), {"BBB": Decimal("100")}),
            PriceObservation(date(2025, 1, 2), {"BBB": Decimal("110")}),
        ]

        with self.assertRaisesRegex(ValueError, "missing symbol"):
            calculate_risk_metrics(self.positions, incomplete_history)

    def test_rejects_non_positive_position_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "quantity must be greater than zero"):
            Position("AAA", Decimal("0"), Decimal("100"), Decimal("110"))

    def test_report_includes_risk_metrics(self) -> None:
        summary = summarize_portfolio(self.positions)
        metrics = calculate_risk_metrics(self.positions, self.history)

        report = format_report(summary, metrics)

        self.assertIn("Annualized volatility:", report)
        self.assertIn("Historical 95% VaR (daily): 8.00%", report)
        self.assertIn("Normal 95% VaR (daily):", report)
        self.assertIn("EWMA annualized volatility (lambda=0.94):", report)
        self.assertIn("Maximum drawdown: -10.00%", report)


if __name__ == "__main__":
    unittest.main()
