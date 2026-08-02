"""Declarative finite-domain schema language used by FinSpace."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .errors import SchemaDefinitionError

JSONValue = str | int | float | bool | None


def _canonical(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise SchemaDefinitionError(f"schema values must be finite JSON values, got {value!r}") from error


def _unique(values: Sequence[JSONValue], label: str) -> tuple[JSONValue, ...]:
    result = tuple(values)
    if not result:
        raise SchemaDefinitionError(f"{label} must contain at least one value")
    keys = [_canonical(value) for value in result]
    if len(keys) != len(set(keys)):
        raise SchemaDefinitionError(f"{label} contains duplicate values")
    return result


@dataclass(frozen=True)
class Condition:
    """A field is active only when a prior field has one of ``values``."""

    field: str
    values: tuple[JSONValue, ...]

    def __post_init__(self) -> None:
        if not self.field:
            raise SchemaDefinitionError("condition field cannot be empty")
        object.__setattr__(self, "values", _unique(self.values, f"condition {self.field}"))

    def matches(self, context: Mapping[str, JSONValue]) -> bool:
        if self.field not in context:
            return False
        key = _canonical(context[self.field])
        return any(_canonical(value) == key for value in self.values)

    def to_dict(self) -> dict[str, Any]:
        return {"field": self.field, "values": list(self.values)}


@dataclass(frozen=True)
class Case:
    """Allowed field values for one value of a dependency field."""

    equals: JSONValue
    values: tuple[JSONValue, ...]

    def __post_init__(self) -> None:
        _canonical(self.equals)
        object.__setattr__(self, "values", _unique(self.values, "case values"))

    def to_dict(self) -> dict[str, Any]:
        return {"equals": self.equals, "values": list(self.values)}


@dataclass(frozen=True)
class Field:
    """One finite field in a scenario schema.

    A field either has an unconditional ``values`` list or a ``depends_on`` field
    with per-value ``cases``. ``when`` conditions can omit the field on paths where
    it is not applicable.
    """

    name: str
    values: tuple[JSONValue, ...] | None = None
    depends_on: str | None = None
    cases: tuple[Case, ...] = ()
    default: tuple[JSONValue, ...] | None = None
    when: tuple[Condition, ...] = ()
    description: str | None = None

    def __post_init__(self) -> None:
        if not self.name or not self.name.replace("_", "a").isalnum():
            raise SchemaDefinitionError(f"invalid field name {self.name!r}")
        if self.values is not None:
            object.__setattr__(self, "values", _unique(self.values, f"field {self.name}"))
        if self.default is not None:
            object.__setattr__(self, "default", _unique(self.default, f"default for {self.name}"))
        if self.depends_on is None:
            if self.values is None:
                raise SchemaDefinitionError(f"field {self.name!r} needs values or depends_on")
            if self.cases or self.default is not None:
                raise SchemaDefinitionError(f"field {self.name!r} cannot define cases without depends_on")
        else:
            if self.values is not None:
                raise SchemaDefinitionError(f"field {self.name!r} cannot combine values and depends_on")
            if not self.cases and self.default is None:
                raise SchemaDefinitionError(f"dependent field {self.name!r} needs cases or a default")
            case_keys = [_canonical(case.equals) for case in self.cases]
            if len(case_keys) != len(set(case_keys)):
                raise SchemaDefinitionError(f"field {self.name!r} has duplicate dependency cases")

    @classmethod
    def enum(
        cls,
        name: str,
        values: Sequence[JSONValue],
        *,
        when: Sequence[Condition] = (),
        description: str | None = None,
    ) -> "Field":
        return cls(name=name, values=tuple(values), when=tuple(when), description=description)

    @classmethod
    def integer(
        cls,
        name: str,
        start: int,
        stop: int,
        *,
        step: int = 1,
        when: Sequence[Condition] = (),
        description: str | None = None,
    ) -> "Field":
        if step <= 0 or stop < start:
            raise SchemaDefinitionError(f"invalid integer range for {name!r}")
        return cls.enum(name, tuple(range(start, stop + 1, step)), when=when, description=description)

    @classmethod
    def dependent(
        cls,
        name: str,
        depends_on: str,
        cases: Mapping[JSONValue, Sequence[JSONValue]] | Sequence[Case],
        *,
        default: Sequence[JSONValue] | None = None,
        when: Sequence[Condition] = (),
        description: str | None = None,
    ) -> "Field":
        normalized = (
            tuple(Case(key, tuple(values)) for key, values in cases.items())
            if isinstance(cases, Mapping)
            else tuple(cases)
        )
        return cls(
            name=name,
            depends_on=depends_on,
            cases=normalized,
            default=tuple(default) if default is not None else None,
            when=tuple(when),
            description=description,
        )

    def is_active(self, context: Mapping[str, JSONValue]) -> bool:
        return all(condition.matches(context) for condition in self.when)

    def resolve_values(self, context: Mapping[str, JSONValue]) -> tuple[JSONValue, ...]:
        if not self.is_active(context):
            return ()
        if self.depends_on is None:
            assert self.values is not None
            return self.values
        if self.depends_on not in context:
            raise SchemaDefinitionError(
                f"field {self.name!r} depends on unresolved field {self.depends_on!r}"
            )
        key = _canonical(context[self.depends_on])
        for case in self.cases:
            if _canonical(case.equals) == key:
                return case.values
        if self.default is not None:
            return self.default
        return ()

    def dependencies(self) -> set[str]:
        result = {condition.field for condition in self.when}
        if self.depends_on:
            result.add(self.depends_on)
        return result

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"name": self.name}
        if self.values is not None:
            result["values"] = list(self.values)
        else:
            result["depends_on"] = self.depends_on
            result["cases"] = [case.to_dict() for case in self.cases]
            if self.default is not None:
                result["default"] = list(self.default)
        if self.when:
            result["when"] = [condition.to_dict() for condition in self.when]
        if self.description:
            result["description"] = self.description
        return result

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "Field":
        when_raw = raw.get("when", ())
        conditions: list[Condition] = []
        if isinstance(when_raw, Mapping):
            for key, values in when_raw.items():
                values_list = values if isinstance(values, list) else [values]
                conditions.append(Condition(str(key), tuple(values_list)))
        else:
            for condition in when_raw:
                conditions.append(Condition(str(condition["field"]), tuple(condition["values"])))

        if "depends_on" not in raw:
            return cls.enum(
                str(raw["name"]),
                tuple(raw["values"]),
                when=conditions,
                description=raw.get("description"),
            )

        cases_raw = raw.get("cases", ())
        cases: list[Case] = []
        if isinstance(cases_raw, Mapping):
            for key, values in cases_raw.items():
                cases.append(Case(key, tuple(values)))
        else:
            for item in cases_raw:
                cases.append(Case(item["equals"], tuple(item["values"])))
        return cls.dependent(
            str(raw["name"]),
            str(raw["depends_on"]),
            cases,
            default=raw.get("default"),
            when=conditions,
            description=raw.get("description"),
        )


@dataclass(frozen=True)
class Schema:
    """A complete finite, ordered, condition-dependent scenario definition."""

    name: str
    fields: tuple[Field, ...]
    version: str = "1"
    description: str | None = None
    metadata: Mapping[str, JSONValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name:
            raise SchemaDefinitionError("schema name cannot be empty")
        object.__setattr__(self, "fields", tuple(self.fields))
        if not self.fields:
            raise SchemaDefinitionError("schema must contain at least one field")
        names = [field.name for field in self.fields]
        if len(names) != len(set(names)):
            raise SchemaDefinitionError("schema field names must be unique")
        previous: set[str] = set()
        for field_spec in self.fields:
            missing = field_spec.dependencies() - previous
            if missing:
                raise SchemaDefinitionError(
                    f"field {field_spec.name!r} references fields that are not earlier in the schema: "
                    + ", ".join(sorted(missing))
                )
            previous.add(field_spec.name)
        for key, value in self.metadata.items():
            if not isinstance(key, str):
                raise SchemaDefinitionError("metadata keys must be strings")
            _canonical(value)

    @property
    def hash(self) -> str:
        payload = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def field(self, name: str) -> Field:
        for field_spec in self.fields:
            if field_spec.name == name:
                return field_spec
        raise SchemaDefinitionError(f"unknown field {name!r}")

    def possible_values(self, name: str) -> tuple[JSONValue, ...]:
        field_spec = self.field(name)
        if field_spec.values is None or field_spec.when:
            raise SchemaDefinitionError(
                f"field {name!r} is conditional; enumerate it through a compiled context instead"
            )
        return field_spec.values

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "name": self.name,
            "version": self.version,
            "fields": [field_spec.to_dict() for field_spec in self.fields],
        }
        if self.description:
            result["description"] = self.description
        if self.metadata:
            result["metadata"] = dict(self.metadata)
        return result

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "Schema":
        return cls(
            name=str(raw["name"]),
            version=str(raw.get("version", "1")),
            description=raw.get("description"),
            metadata=dict(raw.get("metadata", {})),
            fields=tuple(Field.from_dict(item) for item in raw["fields"]),
        )

    @classmethod
    def load(cls, path: str | Path) -> "Schema":
        source = Path(path)
        text = source.read_text(encoding="utf-8")
        if source.suffix.lower() in {".yaml", ".yml"}:
            try:
                import yaml
            except ImportError as error:  # pragma: no cover - dependency is installed normally
                raise SchemaDefinitionError("PyYAML is required to load YAML schemas") from error
            raw = yaml.safe_load(text)
        else:
            raw = json.loads(text)
        if not isinstance(raw, Mapping):
            raise SchemaDefinitionError("schema document must be an object")
        return cls.from_dict(raw)

    def save(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.suffix.lower() in {".yaml", ".yml"}:
            try:
                import yaml
            except ImportError as error:  # pragma: no cover
                raise SchemaDefinitionError("PyYAML is required to save YAML schemas") from error
            target.write_text(yaml.safe_dump(self.to_dict(), sort_keys=False), encoding="utf-8")
        else:
            target.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def relevant_context(self) -> tuple[frozenset[str], ...]:
        """Prior fields that can influence each remaining suffix.

        The compiler uses this to share equivalent suffix states instead of
        materializing the full Cartesian tree.
        """
        relevant: list[frozenset[str]] = [frozenset() for _ in range(len(self.fields) + 1)]
        running: set[str] = set()
        for index in range(len(self.fields) - 1, -1, -1):
            running |= self.fields[index].dependencies()
            relevant[index] = frozenset(running)
        return tuple(relevant)
