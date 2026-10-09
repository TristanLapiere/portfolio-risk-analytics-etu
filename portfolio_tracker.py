"""Portfolio valuation and historical risk analytics using CSV price data."""

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import NormalDist, mean, stdev
from typing import Iterable, TextIO

TRADING_DAYS_PER_YEAR = 252


@dataclass(frozen=True)
class Position:
    symbol: str
    quantity: Decimal
    purchase_price: Decimal
    current_price: Decimal

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("Symbol cannot be empty.")
        for field_name in ("quantity", "purchase_price", "current_price"):
            value = getattr(self, field_name)
            if not value.is_finite() or value <= 0:
                raise ValueError(f"{field_name} must be greater than zero.")

    @property
    def cost_basis(self) -> Decimal:
        return self.quantity * self.purchase_price

    @property
    def market_value(self) -> Decimal:
        return self.quantity * self.current_price

    @property
    def unrealized_pnl(self) -> Decimal:
        return self.market_value - self.cost_basis

    @property
    def return_rate(self) -> Decimal:
        return self.unrealized_pnl / self.cost_basis


@dataclass(frozen=True)
class PortfolioSummary:
    positions: tuple[Position, ...]
    total_cost_basis: Decimal
    total_market_value: Decimal
    total_unrealized_pnl: Decimal
    total_return_rate: Decimal


@dataclass(frozen=True)
class PriceObservation:
    observation_date: date
    closing_prices: dict[str, Decimal]
    adjusted_closing_prices: dict[str, Decimal] | None = None


@dataclass(frozen=True)
class RiskMetrics:
    observation_count: int
    confidence_level: float
    cumulative_return: float
    annualized_volatility: float
    sharpe_ratio: float | None
    historical_var: float
    expected_shortfall: float
    parametric_var: float
    parametric_expected_shortfall: float
    ewma_volatility: float
    sortino_ratio: float | None
    calmar_ratio: float | None
    max_drawdown: float
    asset_volatility: dict[str, float]
    risk_contribution_pct: dict[str, float]
    correlation_matrix: dict[str, dict[str, float | None]]


def _positive_decimal(
    value: str | None,
    field: str,
    row_number: int,
    decimal_comma: bool = False,
) -> Decimal:
    normalized_value = (value or "").strip()
    if decimal_comma and "," in normalized_value and "." not in normalized_value:
        normalized_value = normalized_value.replace(",", ".")
    try:
        parsed = Decimal(normalized_value)
    except (InvalidOperation, TypeError) as error:
        raise ValueError(
            f"Row {row_number}: {field} must be a valid number, got {value!r}."
        ) from error
    if not parsed.is_finite() or parsed <= 0:
        raise ValueError(f"Row {row_number}: {field} must be greater than zero.")
    return parsed


def load_portfolio_data(source: Path | TextIO) -> tuple[list[Position], list[PriceObservation]]:
    """Load positions and dated prices from one long-format CSV.

    Required columns are date,symbol,close,quantity. Each symbol must have one
    positive, constant quantity and one closing price on every observation date.
    An optional adjusted_close column is used for dividend-adjusted returns while
    close remains the actual market price for portfolio valuation.
    """
    required_columns = {"date", "symbol", "close", "quantity"}

    def parse(
        reader: csv.DictReader, decimal_comma: bool
    ) -> tuple[list[Position], list[PriceObservation]]:
        fieldnames = reader.fieldnames or []
        normalized = [name.strip().lower() for name in fieldnames]
        if len(normalized) != len(set(normalized)):
            raise ValueError("CSV contains duplicate column names.")
        missing = required_columns - set(normalized)
        if missing:
            raise ValueError(
                "CSV is missing required column(s): " + ", ".join(sorted(missing)) + "."
            )
        column_names = dict(zip(normalized, fieldnames))

        quantities: dict[str, Decimal] = {}
        prices_by_date: dict[date, dict[str, Decimal]] = {}
        adjusted_prices_by_date: dict[date, dict[str, Decimal]] = {}
        adjusted_close_column = column_names.get("adjusted_close")
        for row_number, row in enumerate(reader, start=2):
            symbol = (row.get(column_names["symbol"]) or "").strip()
            if not symbol:
                raise ValueError(f"Row {row_number}: symbol cannot be empty.")
            try:
                observation_date = date.fromisoformat(
                    (row.get(column_names["date"]) or "").strip()
                )
            except ValueError as error:
                raise ValueError(
                    f"Row {row_number}: date must use YYYY-MM-DD format."
                ) from error

            close = _positive_decimal(
                row.get(column_names["close"], ""),
                "close",
                row_number,
                decimal_comma,
            )
            quantity = _positive_decimal(
                row.get(column_names["quantity"], ""),
                "quantity",
                row_number,
                decimal_comma,
            )
            if symbol in quantities and quantities[symbol] != quantity:
                raise ValueError(
                    f"Row {row_number}: quantity for {symbol} must be constant "
                    "throughout the file."
                )
            quantities[symbol] = quantity

            date_prices = prices_by_date.setdefault(observation_date, {})
            if symbol in date_prices:
                raise ValueError(
                    f"Row {row_number}: duplicate price for {symbol} on "
                    f"{observation_date.isoformat()}."
                )
            date_prices[symbol] = close
            if adjusted_close_column is not None:
                adjusted_prices_by_date.setdefault(observation_date, {})[
                    symbol
                ] = _positive_decimal(
                    row.get(adjusted_close_column, ""),
                    "adjusted_close",
                    row_number,
                    decimal_comma,
                )

        if not prices_by_date:
            raise ValueError("CSV contains no price observations.")
        symbols = set(quantities)
        observations = [
            PriceObservation(
                observation_date,
                prices,
                adjusted_prices_by_date.get(observation_date),
            )
            for observation_date, prices in sorted(prices_by_date.items())
        ]
        for observation in observations:
            missing_symbols = symbols - observation.closing_prices.keys()
            if missing_symbols:
                raise ValueError(
                    f"{observation.observation_date.isoformat()}: missing price(s) "
                    "for " + ", ".join(sorted(missing_symbols)) + "."
                )
            if observation.adjusted_closing_prices is not None:
                missing_adjusted_symbols = (
                    symbols - observation.adjusted_closing_prices.keys()
                )
                if missing_adjusted_symbols:
                    raise ValueError(
                        f"{observation.observation_date.isoformat()}: missing "
                        "adjusted_close value(s) for "
                        + ", ".join(sorted(missing_adjusted_symbols))
                        + "."
                    )
        if len(observations) < 3:
            raise ValueError(
                "CSV must contain at least three distinct dates to calculate "
                "sample covariance."
            )

        positions = [
            Position(
                symbol=symbol,
                quantity=quantities[symbol],
                purchase_price=observations[0].closing_prices[symbol],
                current_price=observations[-1].closing_prices[symbol],
            )
            for symbol in sorted(symbols)
        ]
        return positions, observations

    if isinstance(source, Path):
        try:
            with source.open(newline="", encoding="utf-8-sig") as csv_file:
                sample = csv_file.read(4096)
                csv_file.seek(0)
                delimiter = _detect_delimiter(sample)
                return parse(
                    csv.DictReader(csv_file, delimiter=delimiter),
                    decimal_comma=delimiter == ";",
                )
        except OSError as error:
            raise ValueError(f"Could not read portfolio data {source}: {error}") from error
    sample = source.read(4096)
    source.seek(0)
    delimiter = _detect_delimiter(sample)
    return parse(
        csv.DictReader(source, delimiter=delimiter), decimal_comma=delimiter == ";"
    )


def _detect_delimiter(sample: str) -> str:
    header = sample.splitlines()[0] if sample.splitlines() else ""
    return ";" if header.count(";") > header.count(",") else ","


def load_positions(csv_path: Path) -> list[Position]:
    """Load validated positions from a CSV with the required headers."""
    required_columns = {"symbol", "quantity", "purchase_price", "current_price"}
    try:
        with csv_path.open(newline="", encoding="utf-8-sig") as csv_file:
            reader = csv.DictReader(csv_file)
            columns = set(reader.fieldnames or ())
            missing_columns = required_columns - columns
            if missing_columns:
                missing = ", ".join(sorted(missing_columns))
                raise ValueError(f"CSV is missing required column(s): {missing}.")

            positions: list[Position] = []
            for row_number, row in enumerate(reader, start=2):
                symbol = (row.get("symbol") or "").strip()
                if not symbol:
                    raise ValueError(f"Row {row_number}: symbol cannot be empty.")
                positions.append(
                    Position(
                        symbol=symbol,
                        quantity=_positive_decimal(
                            row.get("quantity", ""), "quantity", row_number
                        ),
                        purchase_price=_positive_decimal(
                            row.get("purchase_price", ""),
                            "purchase_price",
                            row_number,
                        ),
                        current_price=_positive_decimal(
                            row.get("current_price", ""),
                            "current_price",
                            row_number,
                        ),
                    )
                )
    except OSError as error:
        raise ValueError(f"Could not read portfolio file {csv_path}: {error}") from error

    if not positions:
        raise ValueError("Portfolio CSV contains no positions.")
    symbols = [position.symbol for position in positions]
    if len(symbols) != len(set(symbols)):
        raise ValueError("Portfolio contains duplicate symbols.")
    return positions


def load_price_history(
    csv_path: Path, symbols: Iterable[str]
) -> list[PriceObservation]:
    """Load dated closing prices from a wide CSV: date,symbol1,symbol2,..."""
    required_symbols = set(symbols)
    try:
        with csv_path.open(newline="", encoding="utf-8-sig") as csv_file:
            reader = csv.DictReader(csv_file)
            fieldnames = reader.fieldnames or []
            if not fieldnames or fieldnames[0].strip().lower() != "date":
                raise ValueError("Price history CSV must start with a 'date' column.")

            available_symbols = {name.strip() for name in fieldnames[1:]}
            missing_symbols = required_symbols - available_symbols
            if missing_symbols:
                missing = ", ".join(sorted(missing_symbols))
                raise ValueError(f"Price history CSV is missing symbol(s): {missing}.")

            observations: list[PriceObservation] = []
            previous_date: date | None = None
            for row_number, row in enumerate(reader, start=2):
                date_text = (row.get(fieldnames[0]) or "").strip()
                try:
                    observation_date = date.fromisoformat(date_text)
                except ValueError as error:
                    raise ValueError(
                        f"Row {row_number}: date must use YYYY-MM-DD format."
                    ) from error
                if previous_date is not None and observation_date <= previous_date:
                    raise ValueError(
                        f"Row {row_number}: dates must be strictly increasing."
                    )

                prices = {
                    symbol: _positive_decimal(
                        row.get(symbol, ""), f"price for {symbol}", row_number
                    )
                    for symbol in required_symbols
                }
                observations.append(
                    PriceObservation(observation_date, prices)
                )
                previous_date = observation_date
    except OSError as error:
        raise ValueError(f"Could not read price history {csv_path}: {error}") from error

    if len(observations) < 2:
        raise ValueError("Price history must contain at least two dated observations.")
    return observations


def summarize_portfolio(positions: Iterable[Position]) -> PortfolioSummary:
    position_list = tuple(positions)
    if not position_list:
        raise ValueError("Cannot summarize an empty portfolio.")

    total_cost_basis = sum(
        (position.cost_basis for position in position_list), Decimal("0")
    )
    total_market_value = sum(
        (position.market_value for position in position_list), Decimal("0")
    )
    total_unrealized_pnl = total_market_value - total_cost_basis
    return PortfolioSummary(
        positions=position_list,
        total_cost_basis=total_cost_basis,
        total_market_value=total_market_value,
        total_unrealized_pnl=total_unrealized_pnl,
        total_return_rate=total_unrealized_pnl / total_cost_basis,
    )


def portfolio_total_return_values(
    positions: Iterable[Position], price_history: Iterable[PriceObservation]
) -> list[float]:
    """Build a fixed-quantity portfolio value series using adjusted closes if present."""
    position_list = tuple(positions)
    observations = tuple(price_history)
    if not position_list or len(observations) < 2:
        raise ValueError("At least one position and two price observations are required.")
    symbols = {position.symbol for position in position_list}
    for observation in observations:
        missing = symbols - observation.closing_prices.keys()
        if missing:
            raise ValueError(
                "Price observations are missing symbol(s): "
                + ", ".join(sorted(missing))
                + "."
            )
        if any(
            not observation.closing_prices[symbol].is_finite()
            or observation.closing_prices[symbol] <= 0
            for symbol in symbols
        ):
            raise ValueError("Historical closing prices must be finite and positive.")

    adjusted_flags = [
        observation.adjusted_closing_prices is not None
        for observation in observations
    ]
    if any(adjusted_flags) and not all(adjusted_flags):
        raise ValueError("Adjusted closes must be supplied for every observation.")
    if all(adjusted_flags):
        for observation in observations:
            missing_adjusted = {
                position.symbol for position in position_list
            } - observation.adjusted_closing_prices.keys()
            if missing_adjusted:
                raise ValueError(
                    "Adjusted price observations are missing symbol(s): "
                    + ", ".join(sorted(missing_adjusted))
                    + "."
                )
            if any(
                not observation.adjusted_closing_prices[symbol].is_finite()
                or observation.adjusted_closing_prices[symbol] <= 0
                for symbol in (position.symbol for position in position_list)
            ):
                raise ValueError("Adjusted closing prices must be finite and positive.")

    adjusted_values = [
        sum(
            float(
                position.quantity
                * (
                    observation.adjusted_closing_prices[position.symbol]
                    if all(adjusted_flags)
                    else observation.closing_prices[position.symbol]
                )
            )
            for position in position_list
        )
        for observation in observations
    ]
    if not all(adjusted_flags):
        return adjusted_values

    raw_initial_value = sum(
        float(position.quantity * observations[0].closing_prices[position.symbol])
        for position in position_list
    )
    scale = raw_initial_value / adjusted_values[0]
    return [value * scale for value in adjusted_values]


def calculate_risk_metrics(
    positions: Iterable[Position],
    price_history: Iterable[PriceObservation],
    annual_risk_free_rate: float = 0.0,
    confidence_level: float = 0.95,
) -> RiskMetrics:
    """Calculate portfolio history, VaR, drawdown, and asset-level risk analytics.

    Historical portfolio returns use fixed-quantity market weights and adjusted
    closes when supplied. Risk contributions and correlations use sample
    covariance of asset returns with latest raw-market-value weights, annualized
    using 252 trading days. This decomposition describes current-weight risk;
    it is not a forecast.
    """
    position_list = tuple(positions)
    observations = tuple(price_history)
    if not position_list:
        raise ValueError("Cannot calculate risk for an empty portfolio.")
    if len(observations) < 2:
        raise ValueError("Risk analysis requires at least two price observations.")
    if not math.isfinite(annual_risk_free_rate) or annual_risk_free_rate < 0:
        raise ValueError("Annual risk-free rate must be finite and non-negative.")
    if (
        not math.isfinite(confidence_level)
        or not 0 < confidence_level < 1
    ):
        raise ValueError("Confidence level must be strictly between 0 and 1.")

    symbols = sorted(position.symbol for position in position_list)
    position_by_symbol = {position.symbol: position for position in position_list}
    for observation in observations:
        missing = set(symbols) - observation.closing_prices.keys()
        if missing:
            raise ValueError(
                "Price observations are missing symbol(s): "
                + ", ".join(sorted(missing))
                + "."
            )
        if any(
            not observation.closing_prices[symbol].is_finite()
            or observation.closing_prices[symbol] <= 0
            for symbol in symbols
        ):
            raise ValueError("Historical closing prices must be finite and positive.")

    portfolio_values = portfolio_total_return_values(position_list, observations)
    has_adjusted_closes = all(
        observation.adjusted_closing_prices is not None
        for observation in observations
    )
    if any(
        observation.adjusted_closing_prices is not None
        for observation in observations
    ) and not has_adjusted_closes:
        raise ValueError("Adjusted closes must be supplied for every observation.")
    asset_returns = {
        symbol: [
            float(
                current_prices[symbol] / previous_prices[symbol] - 1
            )
            for previous, current in zip(observations, observations[1:])
            for previous_prices, current_prices in [
                (
                    previous.adjusted_closing_prices
                    if has_adjusted_closes
                    else previous.closing_prices,
                    current.adjusted_closing_prices
                    if has_adjusted_closes
                    else current.closing_prices,
                )
            ]
        ]
        for symbol in symbols
    }
    daily_returns = [
        current / previous - 1.0
        for previous, current in zip(portfolio_values, portfolio_values[1:])
    ]
    if not all(math.isfinite(value) for value in daily_returns):
        raise ValueError("Calculated returns contain non-finite values.")

    if len(daily_returns) < 2:
        annualized_volatility = 0.0
        annualized_mean_return = 0.0
        sharpe_ratio = None
        sortino_ratio = None
        return_quantile = 0.0
        tail_returns: list[float] = []
        daily_volatility = 0.0
    else:
        daily_volatility = stdev(daily_returns)
        annualized_volatility = daily_volatility * math.sqrt(TRADING_DAYS_PER_YEAR)
        annualized_mean_return = mean(daily_returns) * TRADING_DAYS_PER_YEAR
        sharpe_ratio = (
            (annualized_mean_return - annual_risk_free_rate) / annualized_volatility
            if annualized_volatility > 0
            else None
        )
        downside_deviation = math.sqrt(
            mean(min(value, 0.0) ** 2 for value in daily_returns)
        )
        sortino_ratio = (
            (annualized_mean_return - annual_risk_free_rate)
            / (downside_deviation * math.sqrt(TRADING_DAYS_PER_YEAR))
            if downside_deviation > 0
            else None
        )

        ordered_returns = sorted(daily_returns)
        tail_probability = 1.0 - confidence_level
        percentile_position = tail_probability * (len(ordered_returns) - 1)
        lower_index = math.floor(percentile_position)
        upper_index = math.ceil(percentile_position)
        fractional_part = percentile_position - lower_index
        return_quantile = (
            ordered_returns[lower_index] * (1.0 - fractional_part)
            + ordered_returns[upper_index] * fractional_part
        )
        tail_returns = [value for value in daily_returns if value <= return_quantile]

    ewma_variance = daily_returns[0] ** 2 if daily_returns else 0.0
    for daily_return in daily_returns[1:]:
        ewma_variance = 0.94 * ewma_variance + 0.06 * daily_return**2
    ewma_volatility = math.sqrt(ewma_variance * TRADING_DAYS_PER_YEAR)
    normal_distribution = NormalDist()
    normal_quantile = normal_distribution.inv_cdf(confidence_level)
    normal_es_multiplier = (
        math.exp(-0.5 * normal_quantile**2)
        / math.sqrt(2.0 * math.pi)
        / (1.0 - confidence_level)
    )
    parametric_var = max(
        0.0, -(mean(daily_returns) - normal_quantile * daily_volatility)
    ) if daily_returns else 0.0
    parametric_expected_shortfall = max(
        0.0,
        -mean(daily_returns) + normal_es_multiplier * daily_volatility,
    ) if daily_returns else 0.0

    asset_volatility: dict[str, float] = {}
    risk_contribution_pct: dict[str, float] = {}
    correlation_matrix: dict[str, dict[str, float | None]] = {}
    if len(daily_returns) >= 2:
        asset_means = {symbol: mean(asset_returns[symbol]) for symbol in symbols}
        covariance = {
            left: {
                right: sum(
                    (left_value - asset_means[left])
                    * (right_value - asset_means[right])
                    for left_value, right_value in zip(
                        asset_returns[left], asset_returns[right]
                    )
                )
                / (len(daily_returns) - 1)
                for right in symbols
            }
            for left in symbols
        }
        latest_values = {
            symbol: float(
                position_by_symbol[symbol].quantity
                * observations[-1].closing_prices[symbol]
            )
            for symbol in symbols
        }
        latest_total = sum(latest_values.values())
        weights = {symbol: latest_values[symbol] / latest_total for symbol in symbols}
        annualized_covariance = {
            left: {
                right: covariance[left][right] * TRADING_DAYS_PER_YEAR
                for right in symbols
            }
            for left in symbols
        }
        portfolio_variance = sum(
            weights[left] * weights[right] * annualized_covariance[left][right]
            for left in symbols
            for right in symbols
        )
        portfolio_variance = max(0.0, portfolio_variance)
        portfolio_model_volatility = math.sqrt(portfolio_variance)

        asset_volatility = {
            symbol: math.sqrt(
                max(0.0, annualized_covariance[symbol][symbol])
            )
            for symbol in symbols
        }
        correlation_matrix = {
            left: {
                right: (
                    covariance[left][right]
                    / math.sqrt(covariance[left][left] * covariance[right][right])
                    if covariance[left][left] > 0 and covariance[right][right] > 0
                    else None
                )
                for right in symbols
            }
            for left in symbols
        }
        if portfolio_model_volatility > 0:
            risk_contribution_pct = {
                symbol: (
                    weights[symbol]
                    * sum(
                        annualized_covariance[symbol][other] * weights[other]
                        for other in symbols
                    )
                    / portfolio_variance
                )
                for symbol in symbols
            }

    peak = portfolio_values[0]
    drawdowns: list[float] = []
    for value in portfolio_values:
        peak = max(peak, value)
        drawdowns.append(value / peak - 1.0)

    expected_shortfall = max(0.0, -mean(tail_returns)) if tail_returns else 0.0
    max_drawdown = min(drawdowns)
    annualized_compound_return = (
        (portfolio_values[-1] / portfolio_values[0])
        ** (TRADING_DAYS_PER_YEAR / len(daily_returns))
        - 1.0
    )
    return RiskMetrics(
        observation_count=len(observations),
        confidence_level=confidence_level,
        cumulative_return=portfolio_values[-1] / portfolio_values[0] - 1.0,
        annualized_volatility=annualized_volatility,
        sharpe_ratio=sharpe_ratio,
        historical_var=max(0.0, -return_quantile),
        expected_shortfall=expected_shortfall,
        parametric_var=parametric_var,
        parametric_expected_shortfall=parametric_expected_shortfall,
        ewma_volatility=ewma_volatility,
        sortino_ratio=sortino_ratio,
        calmar_ratio=(
            annualized_compound_return / abs(max_drawdown)
            if max_drawdown < 0
            else None
        ),
        max_drawdown=max_drawdown,
        asset_volatility=asset_volatility,
        risk_contribution_pct=risk_contribution_pct,
        correlation_matrix=correlation_matrix,
    )

def format_report(
    summary: PortfolioSummary, risk_metrics: RiskMetrics | None = None
) -> str:
    lines = [
        f"{'SYMBOL':<12}{'MARKET VALUE':>16}{'WEIGHT':>12}"
        f"{'UNREALIZED P&L':>18}{'RETURN':>12}",
        "-" * 70,
    ]
    for position in summary.positions:
        weight = position.market_value / summary.total_market_value
        lines.append(
            f"{position.symbol:<12}"
            f"{position.market_value:>16,.2f}"
            f"{weight:>11.2%}"
            f"{position.unrealized_pnl:>18,.2f}"
            f"{position.return_rate:>11.2%}"
        )

    lines.extend(
        [
            "-" * 70,
            f"Cost basis: {summary.total_cost_basis:,.2f}",
            f"Market value: {summary.total_market_value:,.2f}",
            f"Unrealized P&L: {summary.total_unrealized_pnl:,.2f}",
            f"Price-only portfolio return: {summary.total_return_rate:.2%}",
        ]
    )
    if risk_metrics is not None:
        sharpe = (
            f"{risk_metrics.sharpe_ratio:.2f}"
            if risk_metrics.sharpe_ratio is not None
            else "N/A (zero volatility)"
        )
        lines.extend(
            [
                "",
                f"Historical observations: {risk_metrics.observation_count}",
                f"Historical cumulative return: {risk_metrics.cumulative_return:.2%}",
                f"Annualized volatility: {risk_metrics.annualized_volatility:.2%}",
                f"Annualized Sharpe ratio: {sharpe}",
                f"Historical {risk_metrics.confidence_level:.0%} VaR (daily): "
                f"{risk_metrics.historical_var:.2%}",
                f"Historical {risk_metrics.confidence_level:.0%} expected shortfall (daily): "
                f"{risk_metrics.expected_shortfall:.2%}",
                f"Normal {risk_metrics.confidence_level:.0%} VaR (daily): "
                f"{risk_metrics.parametric_var:.2%}",
                f"Normal {risk_metrics.confidence_level:.0%} expected shortfall (daily): "
                f"{risk_metrics.parametric_expected_shortfall:.2%}",
                f"EWMA annualized volatility (lambda=0.94): "
                f"{risk_metrics.ewma_volatility:.2%}",
                "Annualized Sortino ratio: "
                f"{risk_metrics.sortino_ratio:.2f}"
                if risk_metrics.sortino_ratio is not None
                else "Annualized Sortino ratio: N/A",
                "Calmar ratio: "
                f"{risk_metrics.calmar_ratio:.2f}"
                if risk_metrics.calmar_ratio is not None
                else "Calmar ratio: N/A",
                f"Maximum drawdown: {risk_metrics.max_drawdown:.2%}",
                "Risk metrics use adjusted_close for total-return estimates when "
                "provided; otherwise returns are price-only. Position P&L uses raw "
                "closing prices. Costs, rebalancing, taxes, and external cash flows "
                "are excluded.",
            ]
        )
        if risk_metrics.risk_contribution_pct:
            lines.extend(["", "Euler risk contribution by holding:"])
            for symbol, contribution in risk_metrics.risk_contribution_pct.items():
                volatility = risk_metrics.asset_volatility[symbol]
                lines.append(
                    f"  {symbol:<10} volatility {volatility:.2%} | "
                    f"portfolio risk contribution {contribution:.2%}"
                )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze portfolio returns and historical risk from one CSV."
    )
    parser.add_argument("csv_file", type=Path, help="Long-format portfolio data CSV")
    parser.add_argument(
        "--risk-free-rate",
        type=float,
        default=0.0,
        help="Annual risk-free rate as a decimal, e.g. 0.03 for 3%% (default: 0)",
    )
    arguments = parser.parse_args()

    try:
        positions, history = load_portfolio_data(arguments.csv_file)
        summary = summarize_portfolio(positions)
        risk_metrics = calculate_risk_metrics(
            positions, history, arguments.risk_free_rate
        )
    except ValueError as error:
        parser.error(str(error))

    print(format_report(summary, risk_metrics))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
