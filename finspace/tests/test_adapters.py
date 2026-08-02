from __future__ import annotations

import pytest

from finspace.adapters import ISO20022PaymentBuilder, QuantLibEuropeanOptionPricer, SimpleFixNewOrderSingleEncoder


def test_simplefix_adapter() -> None:
    pytest.importorskip("simplefix")
    encoded = SimpleFixNewOrderSingleEncoder()(
        {
            "message_type": "D",
            "side": "1",
            "order_type": "2",
            "symbol": "AAPL",
            "quantity": 100,
            "price": 100.0,
            "time_in_force": "0",
        }
    )
    assert b"35=D\x01" in encoded
    assert encoded.endswith(b"\x01")


def test_quantlib_adapter() -> None:
    pytest.importorskip("QuantLib")
    result = QuantLibEuropeanOptionPricer()(
        {
            "option_type": "call",
            "currency": "USD",
            "rate": 0.03,
            "spot": 100.0,
            "strike": 100.0,
            "maturity_days": 90,
            "volatility": 0.2,
            "dividend": 0.0,
            "engine": "analytic",
        }
    )
    assert result["npv"] > 0


def test_iso20022_adapter() -> None:
    pytest.importorskip("lxml")
    payload = ISO20022PaymentBuilder()(
        {
            "message": "pacs.008.001.14",
            "currency": "USD",
            "amount": "100.00",
            "debtor": "A",
            "creditor": "B",
            "day": 10,
            "charge_bearer": "SLEV",
            "priority": "NORM",
        }
    )
    assert b"pacs.008.001.14" in payload
