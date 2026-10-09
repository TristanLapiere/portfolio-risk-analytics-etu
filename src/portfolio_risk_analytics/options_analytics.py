"""Black-Scholes valuation and Greeks for European options."""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import NormalDist


@dataclass(frozen=True)
class OptionValuation:
    theoretical_price: float
    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float


def black_scholes(
    spot: float,
    strike: float,
    time_to_expiry_years: float,
    volatility: float,
    risk_free_rate: float,
    dividend_yield: float = 0.0,
    option_type: str = "call",
) -> OptionValuation:
    """Return European option value and per-underlying-unit Greeks.

    Vega and rho are per 1.00 change in volatility and rate, respectively;
    theta is per year. Rates and volatility are continuously compounded.
    """
    values = {
        "spot": spot,
        "strike": strike,
        "time to expiry": time_to_expiry_years,
        "volatility": volatility,
        "risk-free rate": risk_free_rate,
        "dividend yield": dividend_yield,
    }
    if any(not math.isfinite(value) for value in values.values()):
        raise ValueError("Option inputs must all be finite numbers.")
    if spot <= 0 or strike <= 0:
        raise ValueError("Spot and strike prices must be greater than zero.")
    if time_to_expiry_years <= 0:
        raise ValueError("Time to expiry must be greater than zero.")
    if volatility <= 0:
        raise ValueError("Volatility must be greater than zero.")
    if dividend_yield < 0:
        raise ValueError("Dividend yield cannot be negative.")
    if option_type not in {"call", "put"}:
        raise ValueError("Option type must be 'call' or 'put'.")

    root_time = math.sqrt(time_to_expiry_years)
    sigma_root_time = volatility * root_time
    d1 = (
        math.log(spot / strike)
        + (risk_free_rate - dividend_yield + 0.5 * volatility**2)
        * time_to_expiry_years
    ) / sigma_root_time
    d2 = d1 - sigma_root_time
    normal = NormalDist()
    density_d1 = math.exp(-0.5 * d1**2) / math.sqrt(2.0 * math.pi)
    discounted_spot = spot * math.exp(-dividend_yield * time_to_expiry_years)
    discounted_strike = strike * math.exp(-risk_free_rate * time_to_expiry_years)
    dividend_discount = math.exp(-dividend_yield * time_to_expiry_years)

    if option_type == "call":
        price = discounted_spot * normal.cdf(d1) - discounted_strike * normal.cdf(d2)
        delta = dividend_discount * normal.cdf(d1)
        theta = (
            -discounted_spot * density_d1 * volatility / (2.0 * root_time)
            - risk_free_rate * discounted_strike * normal.cdf(d2)
            + dividend_yield * discounted_spot * normal.cdf(d1)
        )
        rho = (
            strike
            * time_to_expiry_years
            * math.exp(-risk_free_rate * time_to_expiry_years)
            * normal.cdf(d2)
        )
    else:
        price = (
            discounted_strike * normal.cdf(-d2)
            - discounted_spot * normal.cdf(-d1)
        )
        delta = dividend_discount * (normal.cdf(d1) - 1.0)
        theta = (
            -discounted_spot * density_d1 * volatility / (2.0 * root_time)
            + risk_free_rate * discounted_strike * normal.cdf(-d2)
            - dividend_yield * discounted_spot * normal.cdf(-d1)
        )
        rho = (
            -strike
            * time_to_expiry_years
            * math.exp(-risk_free_rate * time_to_expiry_years)
            * normal.cdf(-d2)
        )

    gamma = dividend_discount * density_d1 / (spot * sigma_root_time)
    vega = discounted_spot * density_d1 * root_time
    return OptionValuation(price, delta, gamma, vega, theta, rho)
