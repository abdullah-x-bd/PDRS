"""FinSpace exception hierarchy."""


class FinSpaceError(Exception):
    """Base class for all FinSpace errors."""


class SchemaDefinitionError(FinSpaceError, ValueError):
    """Raised when a high-level FinSpace schema is invalid."""


class RecordValidationError(FinSpaceError, ValueError):
    """Raised when a record does not belong to a compiled space."""


class RankOutOfRangeError(FinSpaceError, IndexError):
    """Raised when a rank falls outside a space."""


class MissingOptionalDependency(FinSpaceError, ImportError):
    """Raised when an optional adapter dependency is not installed."""


class CheckpointError(FinSpaceError):
    """Raised for incompatible or corrupt execution checkpoints."""
