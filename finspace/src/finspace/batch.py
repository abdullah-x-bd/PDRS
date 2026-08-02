"""Batch conversion helpers for generated finance records."""

from __future__ import annotations

from collections import OrderedDict
from typing import Any, Mapping, Sequence

from .errors import MissingOptionalDependency


def records_to_columns(records: Sequence[Mapping[str, Any]]) -> dict[str, list[Any]]:
    fields: OrderedDict[str, None] = OrderedDict()
    for record in records:
        for key in record:
            fields.setdefault(key, None)
    return {field: [record.get(field) for record in records] for field in fields}


def to_numpy(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    try:
        import numpy as np
    except ImportError as error:
        raise MissingOptionalDependency("install finspace[tabular] for NumPy output") from error
    columns = records_to_columns(records)
    return {name: np.asarray(values) for name, values in columns.items()}


def to_pandas(records: Sequence[Mapping[str, Any]]) -> Any:
    try:
        import pandas as pd
    except ImportError as error:
        raise MissingOptionalDependency("install finspace[tabular] for pandas output") from error
    return pd.DataFrame.from_records(records)


def to_arrow(records: Sequence[Mapping[str, Any]]) -> Any:
    try:
        import pyarrow as pa
    except ImportError as error:
        raise MissingOptionalDependency("install finspace[arrow] for Arrow output") from error
    return pa.Table.from_pylist([dict(record) for record in records])
