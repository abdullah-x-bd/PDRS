from __future__ import annotations

from finspace.templates import european_option_space, fix_order_space, iso20022_payment_space


def test_option_template() -> None:
    space = european_option_space(
        currencies=("USD",),
        spots=(100.0,),
        strikes=(100.0,),
        maturities_days=(30,),
        volatilities=(0.2,),
        dividends=(0.0,),
        rates_by_currency={"USD": (0.01, 0.03)},
    )
    assert space.count == 2 * 1 * 2 * 1 * 1 * 1 * 1 * 1 * 3


def test_fix_template_conditions() -> None:
    space = fix_order_space(symbols=("AAPL",), quantities=(100,), prices=(100.0,), stop_prices=(90.0,))
    records = list(space.enumerate())
    market = next(record for record in records if record["order_type"] == "1")
    limit = next(record for record in records if record["order_type"] == "2")
    stop = next(record for record in records if record["order_type"] == "3")
    stop_limit = next(record for record in records if record["order_type"] == "4")
    assert "price" not in market and "stop_price" not in market
    assert "price" in limit and "stop_price" not in limit
    assert "stop_price" in stop and "price" not in stop
    assert "price" in stop_limit and "stop_price" in stop_limit


def test_iso_template() -> None:
    space = iso20022_payment_space(
        currencies=("USD",), amount_buckets=("1.00",), parties=("a", "b")
    )
    assert space.count > 0
    for record in space.sample(20, seed=1):
        if record["message"].startswith("pain"):
            assert "batch_booking" in record and "priority" not in record
        else:
            assert "priority" in record and "batch_booking" not in record
