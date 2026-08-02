from __future__ import annotations

from finspace import records_to_columns, to_numpy, to_pandas


RECORDS = [
    {"currency": "USD", "value": 1},
    {"currency": "EUR", "value": 2, "optional": True},
]


def test_records_to_columns() -> None:
    assert records_to_columns(RECORDS) == {
        "currency": ["USD", "EUR"],
        "value": [1, 2],
        "optional": [None, True],
    }


def test_numpy_output() -> None:
    arrays = to_numpy(RECORDS)
    assert arrays["value"].tolist() == [1, 2]


def test_pandas_output() -> None:
    frame = to_pandas(RECORDS)
    assert frame.shape == (2, 3)
