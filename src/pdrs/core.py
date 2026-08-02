from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import random
from typing import Any, Mapping, Sequence

Token = str | int


class SchemaError(ValueError):
    """Raised when a schema or value violates the PDRS model."""


@dataclass(frozen=True)
class TerminalNode:
    name: str


@dataclass(frozen=True)
class ChoiceBranch:
    value: str
    target: str


@dataclass(frozen=True)
class ChoiceNode:
    name: str
    field: str
    branches: tuple[ChoiceBranch, ...]


@dataclass(frozen=True)
class RangeNode:
    name: str
    field: str
    start: int
    stop: int
    target: str


Node = TerminalNode | ChoiceNode | RangeNode


class CompiledSchema:
    """Validated finite acyclic PDRS schema with cached subtree counts."""

    def __init__(self, document: Mapping[str, Any]):
        self.document = json.loads(json.dumps(document))
        self.name = str(document.get("name", "unnamed"))
        self.version = str(document.get("version", "0"))
        self.root = str(document.get("root", ""))
        raw_nodes = document.get("nodes")
        if not self.root:
            raise SchemaError("schema root is required")
        if not isinstance(raw_nodes, Mapping) or not raw_nodes:
            raise SchemaError("schema nodes must be a non-empty mapping")
        self.nodes: dict[str, Node] = {
            str(name): self._parse_node(str(name), raw)
            for name, raw in raw_nodes.items()
        }
        if self.root not in self.nodes:
            raise SchemaError(f"root node {self.root!r} does not exist")
        self._counts: dict[str, int] = {}
        self._validate_graph()
        self._count(self.root)

    @staticmethod
    def _parse_node(name: str, raw: Any) -> Node:
        if not isinstance(raw, Mapping):
            raise SchemaError(f"node {name!r} must be an object")
        kind = raw.get("type")
        if kind == "terminal":
            return TerminalNode(name=name)
        if kind == "choice":
            field = str(raw.get("field", name))
            raw_branches = raw.get("branches")
            if not isinstance(raw_branches, list) or not raw_branches:
                raise SchemaError(f"choice node {name!r} requires branches")
            branches: list[ChoiceBranch] = []
            seen: set[str] = set()
            for item in raw_branches:
                if not isinstance(item, Mapping):
                    raise SchemaError(f"branch in {name!r} must be an object")
                value = str(item.get("value", ""))
                target = str(item.get("target", ""))
                if not value or not target:
                    raise SchemaError(f"branch in {name!r} requires value and target")
                if value in seen:
                    raise SchemaError(f"duplicate choice value {value!r} in {name!r}")
                seen.add(value)
                branches.append(ChoiceBranch(value=value, target=target))
            return ChoiceNode(name=name, field=field, branches=tuple(branches))
        if kind == "range":
            field = str(raw.get("field", name))
            start = raw.get("start")
            stop = raw.get("stop")
            target = str(raw.get("target", ""))
            if not isinstance(start, int) or isinstance(start, bool):
                raise SchemaError(f"range node {name!r} start must be an integer")
            if not isinstance(stop, int) or isinstance(stop, bool):
                raise SchemaError(f"range node {name!r} stop must be an integer")
            if stop < start:
                raise SchemaError(f"range node {name!r} has stop < start")
            if not target:
                raise SchemaError(f"range node {name!r} requires target")
            return RangeNode(name=name, field=field, start=start, stop=stop, target=target)
        raise SchemaError(f"node {name!r} has unsupported type {kind!r}")

    def _targets(self, node: Node) -> tuple[str, ...]:
        if isinstance(node, TerminalNode):
            return ()
        if isinstance(node, ChoiceNode):
            return tuple(branch.target for branch in node.branches)
        return (node.target,)

    def _validate_graph(self) -> None:
        for node in self.nodes.values():
            for target in self._targets(node):
                if target not in self.nodes:
                    raise SchemaError(f"node {node.name!r} targets missing node {target!r}")

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(name: str) -> None:
            if name in visiting:
                raise SchemaError(f"cycle detected at node {name!r}")
            if name in visited:
                return
            visiting.add(name)
            for target in self._targets(self.nodes[name]):
                visit(target)
            visiting.remove(name)
            visited.add(name)

        visit(self.root)
        unreachable = set(self.nodes) - visited
        if unreachable:
            names = ", ".join(sorted(unreachable))
            raise SchemaError(f"unreachable nodes are not allowed: {names}")

    def _count(self, name: str) -> int:
        if name in self._counts:
            return self._counts[name]
        node = self.nodes[name]
        if isinstance(node, TerminalNode):
            total = 1
        elif isinstance(node, ChoiceNode):
            total = sum(self._count(branch.target) for branch in node.branches)
        else:
            width = node.stop - node.start + 1
            total = width * self._count(node.target)
        if total <= 0:
            raise SchemaError(f"node {name!r} has an empty domain")
        self._counts[name] = total
        return total

    @property
    def count(self) -> int:
        return self._counts[self.root]

    @property
    def bit_length(self) -> int:
        return max(0, (self.count - 1).bit_length())

    @property
    def canonical_hash(self) -> str:
        payload = json.dumps(self.document, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def rank(self, value: Sequence[Token]) -> int:
        tokens = list(value)
        position = 0
        node_name = self.root
        rank = 0
        while True:
            node = self.nodes[node_name]
            if isinstance(node, TerminalNode):
                if position != len(tokens):
                    raise SchemaError("value contains trailing tokens after terminal state")
                return rank
            if position >= len(tokens):
                raise SchemaError(f"value ended before field {node.field!r}")
            token = tokens[position]
            position += 1
            if isinstance(node, ChoiceNode):
                if not isinstance(token, str):
                    raise SchemaError(f"field {node.field!r} requires a string choice")
                selected: ChoiceBranch | None = None
                for branch in node.branches:
                    if branch.value == token:
                        selected = branch
                        break
                    rank += self._count(branch.target)
                if selected is None:
                    allowed = ", ".join(branch.value for branch in node.branches)
                    raise SchemaError(f"invalid value {token!r} for {node.field!r}; allowed: {allowed}")
                node_name = selected.target
            else:
                if not isinstance(token, int) or isinstance(token, bool):
                    raise SchemaError(f"field {node.field!r} requires an integer")
                if token < node.start or token > node.stop:
                    raise SchemaError(
                        f"value {token} outside {node.field!r} range {node.start}..{node.stop}"
                    )
                block = self._count(node.target)
                rank += (token - node.start) * block
                node_name = node.target

    def unrank(self, index: int) -> list[Token]:
        if not isinstance(index, int) or isinstance(index, bool):
            raise SchemaError("rank must be an integer")
        if index < 0 or index >= self.count:
            raise SchemaError(f"rank must be in 0..{self.count - 1}")
        node_name = self.root
        output: list[Token] = []
        remainder = index
        while True:
            node = self.nodes[node_name]
            if isinstance(node, TerminalNode):
                if remainder != 0:
                    raise AssertionError("internal unranking remainder invariant failed")
                return output
            if isinstance(node, ChoiceNode):
                for branch in node.branches:
                    block = self._count(branch.target)
                    if remainder < block:
                        output.append(branch.value)
                        node_name = branch.target
                        break
                    remainder -= block
                else:
                    raise AssertionError("internal choice unranking invariant failed")
            else:
                block = self._count(node.target)
                offset, remainder = divmod(remainder, block)
                value = node.start + offset
                if value > node.stop:
                    raise AssertionError("internal range unranking invariant failed")
                output.append(value)
                node_name = node.target

    def sample(self, rng: random.Random | None = None) -> list[Token]:
        source = rng if rng is not None else random.SystemRandom()
        return self.unrank(source.randrange(self.count))

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "count": self.count,
            "minimum_fixed_bits": self.bit_length,
            "nodes": len(self.nodes),
            "canonical_hash": self.canonical_hash,
        }


def load_schema(path: str | Path) -> CompiledSchema:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(document, Mapping):
        raise SchemaError("schema document must be a JSON object")
    return CompiledSchema(document)
