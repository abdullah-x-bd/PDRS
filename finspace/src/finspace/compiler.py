"""Compile high-level FinSpace schemas into exact PDRS domains."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .errors import SchemaDefinitionError
from .schema import JSONValue, Schema, _canonical


@dataclass(frozen=True)
class Compilation:
    document: dict[str, Any]
    fixed: Mapping[str, JSONValue]
    states: int


class SchemaCompiler:
    """State-sharing compiler from declarative fields to finite PDRS choices."""

    def __init__(self, schema: Schema, fixed: Mapping[str, JSONValue] | None = None) -> None:
        self.schema = schema
        self.fixed = dict(fixed or {})
        unknown = set(self.fixed) - {field.name for field in schema.fields}
        if unknown:
            raise SchemaDefinitionError(f"cannot fix unknown fields: {', '.join(sorted(unknown))}")
        self.nodes: dict[str, dict[str, Any]] = {"end": {"type": "terminal"}}
        self.memo: dict[tuple[int, tuple[tuple[str, str], ...]], str | None] = {}
        self.relevant = schema.relevant_context()
        self.counter = 0

    def compile(self) -> Compilation:
        root = self._build(0, {})
        if root is None:
            raise SchemaDefinitionError("field constraints produce an empty domain")
        document = {
            "name": self.schema.name,
            "version": self.schema.version,
            "root": root,
            "nodes": self.nodes,
        }
        return Compilation(document=document, fixed=dict(self.fixed), states=len(self.nodes))

    def _key(self, index: int, context: Mapping[str, JSONValue]) -> tuple[int, tuple[tuple[str, str], ...]]:
        names = self.relevant[index]
        return index, tuple(sorted((name, _canonical(context[name])) for name in names if name in context))

    def _build(self, index: int, context: dict[str, JSONValue]) -> str | None:
        if index == len(self.schema.fields):
            return "end"
        key = self._key(index, context)
        if key in self.memo:
            return self.memo[key]

        field_spec = self.schema.fields[index]
        if not field_spec.is_active(context):
            target = self._build(index + 1, context)
            self.memo[key] = target
            return target

        all_values = field_spec.resolve_values(context)
        if not all_values:
            self.memo[key] = None
            return None
        desired = self.fixed.get(field_spec.name, None)
        has_fixed = field_spec.name in self.fixed
        desired_key = _canonical(desired) if has_fixed else None

        branches: list[dict[str, str]] = []
        for value_index, value in enumerate(all_values):
            if has_fixed and _canonical(value) != desired_key:
                continue
            next_context = dict(context)
            next_context[field_spec.name] = value
            target = self._build(index + 1, next_context)
            if target is not None:
                branches.append({"value": str(value_index), "target": target})

        if not branches:
            self.memo[key] = None
            return None

        node_name = f"s{self.counter}"
        self.counter += 1
        self.nodes[node_name] = {
            "type": "choice",
            "field": field_spec.name,
            "branches": branches,
        }
        self.memo[key] = node_name
        return node_name
