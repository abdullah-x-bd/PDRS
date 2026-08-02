"""FinSpace: exact, rank-addressable financial scenario spaces."""

from .batch import records_to_columns, to_arrow, to_numpy, to_pandas
from .errors import (
    CheckpointError,
    FinSpaceError,
    MissingOptionalDependency,
    RankOutOfRangeError,
    RecordValidationError,
    SchemaDefinitionError,
)
from .schema import Case, Condition, Field, Schema
from .space import Partition, Space

__all__ = [
    "Case",
    "CheckpointError",
    "Condition",
    "Field",
    "FinSpaceError",
    "MissingOptionalDependency",
    "Partition",
    "RankOutOfRangeError",
    "RecordValidationError",
    "Schema",
    "SchemaDefinitionError",
    "Space",
    "records_to_columns",
    "to_arrow",
    "to_numpy",
    "to_pandas",
]

__version__ = "0.1.0"
