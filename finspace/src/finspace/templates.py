"""Ready-to-customize finance scenario templates."""

from __future__ import annotations

from decimal import Decimal
from typing import Sequence

from .schema import Condition, Field, Schema
from .space import Space


def european_option_schema(
    *,
    currencies: Sequence[str] = ("USD", "EUR", "JPY"),
    option_types: Sequence[str] = ("call", "put"),
    spots: Sequence[float] = tuple(float(value) for value in range(50, 151, 5)),
    strikes: Sequence[float] = tuple(float(value) for value in range(50, 151, 5)),
    maturities_days: Sequence[int] = (7, 30, 90, 180, 365, 730),
    volatilities: Sequence[float] = (0.05, 0.10, 0.15, 0.25, 0.40, 0.80),
    dividends: Sequence[float] = (0.00, 0.01, 0.03, 0.07),
    rates_by_currency: dict[str, Sequence[float]] | None = None,
) -> Schema:
    rates = rates_by_currency or {
        "USD": (0.00, 0.01, 0.03, 0.05, 0.08),
        "EUR": (-0.01, 0.00, 0.01, 0.03, 0.05),
        "JPY": (-0.01, 0.00, 0.01, 0.03),
    }
    missing = set(currencies) - set(rates)
    if missing:
        raise ValueError(f"rates_by_currency is missing: {', '.join(sorted(missing))}")
    return Schema(
        name="european-option-scenarios",
        version="1",
        description="Finite European option pricing and testing scenarios.",
        fields=(
            Field.enum("option_type", option_types),
            Field.enum("currency", currencies),
            Field.dependent("rate", "currency", {currency: rates[currency] for currency in currencies}),
            Field.enum("spot", spots),
            Field.enum("strike", strikes),
            Field.enum("maturity_days", maturities_days),
            Field.enum("volatility", volatilities),
            Field.enum("dividend", dividends),
            Field.enum("engine", ("analytic", "binomial", "finite_difference")),
        ),
        metadata={"template": "european_option"},
    )


def european_option_space(**kwargs: object) -> Space:
    return Space(european_option_schema(**kwargs))


def fix_order_schema(
    *,
    symbols: Sequence[str] = ("AAPL", "MSFT", "NVDA", "TSLA", "EUR/USD", "USD/INR"),
    quantities: Sequence[int] = (100, 500, 1000, 5000),
    prices: Sequence[float] = (50.0, 75.0, 100.0, 125.0, 150.0),
    stop_prices: Sequence[float] = (45.0, 70.0, 95.0, 120.0, 145.0),
) -> Schema:
    return Schema(
        name="fix-new-order-single",
        version="1",
        description="Bounded FIX 4.4 New Order Single scenarios.",
        fields=(
            Field.enum("message_type", ("D",)),
            Field.enum("side", ("1", "2")),
            Field.enum("order_type", ("1", "2", "3", "4")),
            Field.enum("symbol", symbols),
            Field.enum("quantity", quantities),
            Field.enum(
                "price",
                prices,
                when=(Condition("order_type", ("2", "4")),),
            ),
            Field.enum(
                "stop_price",
                stop_prices,
                when=(Condition("order_type", ("3", "4")),),
            ),
            Field.enum("time_in_force", ("0", "1", "3", "4", "6")),
        ),
        metadata={"template": "fix_new_order_single", "fix_version": "FIX.4.4"},
    )


def fix_order_space(**kwargs: object) -> Space:
    return Space(fix_order_schema(**kwargs))


def iso20022_payment_schema(
    *,
    currencies: Sequence[str] = ("EUR", "GBP", "USD"),
    amount_buckets: Sequence[Decimal | str | float] = (
        "0.01",
        "1.00",
        "10.00",
        "100.00",
        "1000.00",
        "10000.00",
        "100000.00",
        "1000000.00",
    ),
    parties: Sequence[str] = ("party_0", "party_1", "party_2", "party_3"),
) -> Schema:
    amounts = tuple(str(value) for value in amount_buckets)
    return Schema(
        name="iso20022-payment-scenarios",
        version="1",
        description="Bounded pain.001 and pacs.008 payment scenarios.",
        fields=(
            Field.enum("message", ("pain.001.001.13", "pacs.008.001.14")),
            Field.enum("currency", currencies),
            Field.enum("amount", amounts),
            Field.enum("debtor", parties),
            Field.enum("creditor", parties),
            Field.integer("day", 3, 27),
            Field.enum(
                "batch_booking",
                (True, False),
                when=(Condition("message", ("pain.001.001.13",)),),
            ),
            Field.enum(
                "charge_bearer",
                ("SLEV", "SHAR"),
                when=(Condition("message", ("pacs.008.001.14",)),),
            ),
            Field.enum(
                "priority",
                ("NORM", "HIGH"),
                when=(Condition("message", ("pacs.008.001.14",)),),
            ),
        ),
        metadata={"template": "iso20022_payment"},
    )


def iso20022_payment_space(**kwargs: object) -> Space:
    return Space(iso20022_payment_schema(**kwargs))
