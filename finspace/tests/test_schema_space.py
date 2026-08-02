from __future__ import annotations

import json

import pytest

from finspace import Condition, Field, RecordValidationError, Schema, SchemaDefinitionError, Space


def order_space() -> Space:
    return Space(
        Schema(
            name="orders",
            fields=(
                Field.enum("order_type", ("market", "limit", "stop_limit")),
                Field.enum("symbol", ("AAPL", "MSFT")),
                Field.enum(
                    "price",
                    (90, 100),
                    when=(Condition("order_type", ("limit", "stop_limit")),),
                ),
                Field.enum(
                    "stop",
                    (80, 90),
                    when=(Condition("order_type", ("stop_limit",)),),
                ),
            ),
        )
    )


def test_conditional_count_and_bijection() -> None:
    space = order_space()
    # market: 2, limit: 2*2, stop_limit: 2*2*2
    assert space.count == 14
    records = [space.unrank(rank) for rank in range(space.count)]
    assert len({json.dumps(record, sort_keys=True) for record in records}) == 14
    for rank, record in enumerate(records):
        assert space.rank(record) == rank


def test_inactive_and_missing_fields_are_rejected() -> None:
    space = order_space()
    with pytest.raises(RecordValidationError):
        space.rank({"order_type": "market", "symbol": "AAPL", "price": 100})
    with pytest.raises(RecordValidationError):
        space.rank({"order_type": "limit", "symbol": "AAPL"})


def test_dependent_values() -> None:
    schema = Schema(
        name="rates",
        fields=(
            Field.enum("currency", ("USD", "EUR")),
            Field.dependent("rate", "currency", {"USD": (1, 2, 3), "EUR": (4, 5)}),
        ),
    )
    space = Space(schema)
    assert space.count == 5
    assert space.validate({"currency": "USD", "rate": 3})
    with pytest.raises(RecordValidationError):
        space.rank({"currency": "EUR", "rate": 3})


def test_conditioned_space() -> None:
    space = order_space()
    limits = space.condition(order_type="limit")
    assert limits.count == 4
    for record in limits.enumerate():
        assert record["order_type"] == "limit"
        assert space.unrank(space.rank(record)) == record


def test_schema_validation_order() -> None:
    with pytest.raises(SchemaDefinitionError):
        Schema(
            name="bad",
            fields=(
                Field.dependent("rate", "currency", {"USD": (1,)}),
                Field.enum("currency", ("USD",)),
            ),
        )


def test_schema_round_trip(tmp_path) -> None:
    schema = order_space().schema
    path = tmp_path / "schema.yaml"
    schema.save(path)
    loaded = Schema.load(path)
    assert loaded.to_dict() == schema.to_dict()
    assert loaded.hash == schema.hash
