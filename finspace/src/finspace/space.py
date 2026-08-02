"""Public rank-addressable scenario-space API."""

from __future__ import annotations

from dataclasses import dataclass
import random
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence

from pdrs import CompiledSchema

from .compiler import Compilation, SchemaCompiler
from .errors import RankOutOfRangeError, RecordValidationError
from .schema import JSONValue, Schema, _canonical


@dataclass(frozen=True)
class Partition:
    """A deterministic half-open interval of ranks assigned to one worker."""

    schema_hash: str
    worker_id: int
    worker_count: int
    start: int
    stop: int

    def __len__(self) -> int:
        return self.stop - self.start

    def __iter__(self) -> Iterator[int]:
        return iter(range(self.start, self.stop))

    def batches(self, size: int) -> Iterator[range]:
        if size <= 0:
            raise ValueError("batch size must be positive")
        for start in range(self.start, self.stop, size):
            yield range(start, min(self.stop, start + size))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_hash": self.schema_hash,
            "worker_id": self.worker_id,
            "worker_count": self.worker_count,
            "start": self.start,
            "stop": self.stop,
            "count": len(self),
        }


class Space:
    """An exact finite domain of valid finance records."""

    def __init__(self, schema: Schema, *, fixed: Mapping[str, JSONValue] | None = None) -> None:
        self.schema = schema
        self.fixed = dict(fixed or {})
        self.compilation: Compilation = SchemaCompiler(schema, self.fixed).compile()
        self._compiled = CompiledSchema(self.compilation.document)

    @classmethod
    def load(cls, path: str | Path) -> "Space":
        return cls(Schema.load(path))

    @property
    def count(self) -> int:
        return self._compiled.count

    @property
    def schema_hash(self) -> str:
        return self.schema.hash

    @property
    def engine_hash(self) -> str:
        return self._compiled.canonical_hash

    @property
    def fields(self) -> tuple[str, ...]:
        return tuple(field.name for field in self.schema.fields)

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.schema.name,
            "version": self.schema.version,
            "count": self.count,
            "schema_hash": self.schema_hash,
            "engine_hash": self.engine_hash,
            "compiled_states": self.compilation.states,
            "fixed": dict(self.fixed),
            "fields": [field.to_dict() for field in self.schema.fields],
        }

    def _tokens_from_record(self, record: Mapping[str, JSONValue]) -> list[str]:
        unknown = set(record) - set(self.fields)
        if unknown:
            raise RecordValidationError(f"record contains unknown fields: {', '.join(sorted(unknown))}")
        context: dict[str, JSONValue] = {}
        tokens: list[str] = []
        for field_spec in self.schema.fields:
            active = field_spec.is_active(context)
            if not active:
                if field_spec.name in record:
                    raise RecordValidationError(f"field {field_spec.name!r} is not active for this record")
                continue
            if field_spec.name not in record:
                raise RecordValidationError(f"record is missing active field {field_spec.name!r}")
            value = record[field_spec.name]
            values = field_spec.resolve_values(context)
            key = _canonical(value)
            index = next((i for i, candidate in enumerate(values) if _canonical(candidate) == key), None)
            if index is None:
                raise RecordValidationError(f"value {value!r} is not allowed for field {field_spec.name!r} in this context")
            if field_spec.name in self.fixed and _canonical(self.fixed[field_spec.name]) != key:
                raise RecordValidationError(f"field {field_spec.name!r} must equal conditioned value {self.fixed[field_spec.name]!r}")
            tokens.append(str(index))
            context[field_spec.name] = value
        return tokens

    def _record_from_tokens(self, tokens: Sequence[str | int]) -> dict[str, JSONValue]:
        context: dict[str, JSONValue] = {}
        cursor = 0
        for field_spec in self.schema.fields:
            if not field_spec.is_active(context):
                continue
            if cursor >= len(tokens):
                raise RuntimeError("compiled engine returned too few tokens")
            values = field_spec.resolve_values(context)
            try:
                index = int(tokens[cursor])
                value = values[index]
            except (ValueError, IndexError) as error:
                raise RuntimeError(f"compiled engine returned invalid token {tokens[cursor]!r} for {field_spec.name!r}") from error
            context[field_spec.name] = value
            cursor += 1
        if cursor != len(tokens):
            raise RuntimeError("compiled engine returned trailing tokens")
        return context

    def rank(self, record: Mapping[str, JSONValue]) -> int:
        try:
            return self._compiled.rank(self._tokens_from_record(record))
        except RecordValidationError:
            raise
        except Exception as error:
            raise RecordValidationError(str(error)) from error

    def unrank(self, rank: int) -> dict[str, JSONValue]:
        if isinstance(rank, bool) or not isinstance(rank, int) or rank < 0 or rank >= self.count:
            raise RankOutOfRangeError(f"rank must satisfy 0 <= rank < {self.count}, got {rank!r}")
        return self._record_from_tokens(self._compiled.unrank(rank))

    def validate(self, record: Mapping[str, JSONValue]) -> bool:
        self.rank(record)
        return True

    def explain(self, record: Mapping[str, JSONValue]) -> dict[str, Any]:
        rank = self.rank(record)
        return {"rank": rank, "count": self.count, "fraction": rank / self.count, "schema_hash": self.schema_hash, "engine_hash": self.engine_hash, "record": dict(record)}

    def enumerate(self, start: int = 0, stop: int | None = None) -> Iterator[dict[str, JSONValue]]:
        effective_stop = self.count if stop is None else stop
        if start < 0 or effective_stop < start or effective_stop > self.count:
            raise RankOutOfRangeError("invalid enumeration interval")
        for rank in range(start, effective_stop):
            yield self.unrank(rank)

    def sample(self, n: int = 1, *, replace: bool = False, seed: int | str | bytes | None = None, with_ranks: bool = False) -> list[dict[str, JSONValue]] | list[tuple[int, dict[str, JSONValue]]]:
        if n < 0:
            raise ValueError("sample size cannot be negative")
        if not replace and n > self.count:
            raise ValueError(f"cannot sample {n} unique objects from a domain of {self.count}")
        rng = random.Random(seed)
        ranks = [rng.randrange(self.count) for _ in range(n)] if replace else rng.sample(range(self.count), n)
        if with_ranks:
            return [(rank, self.unrank(rank)) for rank in ranks]
        return [self.unrank(rank) for rank in ranks]

    def condition(self, **fixed: JSONValue) -> "Space":
        combined = dict(self.fixed)
        combined.update(fixed)
        return Space(self.schema, fixed=combined)

    def sample_stratified(self, field: str, n: int, *, seed: int | str | bytes | None = None, with_ranks: bool = False) -> list[dict[str, JSONValue]] | list[tuple[int, dict[str, JSONValue]]]:
        values = list(self.schema.possible_values(field))
        rng = random.Random(seed)
        rng.shuffle(values)
        allocations = [n // len(values)] * len(values)
        for index in range(n % len(values)):
            allocations[index] += 1
        output: list[tuple[int, dict[str, JSONValue]]] = []
        for value, allocation in zip(values, allocations):
            subspace = self.condition(**{field: value})
            if allocation > subspace.count:
                raise ValueError(f"stratum {field}={value!r} has only {subspace.count} objects, needs {allocation}")
            for record in subspace.sample(allocation, replace=False, seed=rng.randrange(2**63)):
                output.append((self.rank(record), record))
        rng.shuffle(output)
        if with_ranks:
            return output
        return [record for _, record in output]

    def partition(self, worker_id: int, worker_count: int) -> Partition:
        if worker_count <= 0:
            raise ValueError("worker_count must be positive")
        if worker_id < 0 or worker_id >= worker_count:
            raise ValueError("worker_id must satisfy 0 <= worker_id < worker_count")
        start = (worker_id * self.count) // worker_count
        stop = ((worker_id + 1) * self.count) // worker_count
        return Partition(self.schema_hash, worker_id, worker_count, start, stop)

    def partitions(self, worker_count: int) -> tuple[Partition, ...]:
        return tuple(self.partition(worker, worker_count) for worker in range(worker_count))

    def unrank_many(self, ranks: Iterable[int]) -> list[dict[str, JSONValue]]:
        return [self.unrank(rank) for rank in ranks]
