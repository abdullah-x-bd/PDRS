from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import random
from typing import Any, Iterator, Mapping, Sequence

Token = str | int


class SchemaError(ValueError):
    """Raised when a schema or value violates the PDRS model."""


@dataclass(frozen=True)
class SchemaLimits:
    max_nodes: int = 100_000
    max_depth: int = 10_000
    max_range_width: int = 10**12
    max_domain_bits: int = 1_000_000


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
    """Validated finite acyclic PDRS schema with exact counting and ranking."""

    def __init__(
        self,
        document: Mapping[str, Any],
        *,
        limits: SchemaLimits | None = None,
    ):
        self.limits = limits or SchemaLimits()
        self.document = json.loads(json.dumps(document))
        self.name = str(document.get("name", "unnamed"))
        self.version = str(document.get("version", "0"))
        self.root = str(document.get("root", ""))
        raw_nodes = document.get("nodes")
        if not self.root:
            raise SchemaError("schema root is required")
        if not isinstance(raw_nodes, Mapping) or not raw_nodes:
            raise SchemaError("schema nodes must be a non-empty mapping")
        if len(raw_nodes) > self.limits.max_nodes:
            raise SchemaError(
                f"schema has {len(raw_nodes)} nodes, exceeding limit {self.limits.max_nodes}"
            )
        self.nodes: dict[str, Node] = {
            str(name): self._parse_node(str(name), raw)
            for name, raw in raw_nodes.items()
        }
        if self.root not in self.nodes:
            raise SchemaError(f"root node {self.root!r} does not exist")

        self._counts: dict[str, int] = {}
        self._depths: dict[str, int] = {}
        self._choice_lookup: dict[str, dict[str, tuple[str, int]]] = {}
        self._choice_ends: dict[str, tuple[int, ...]] = {}
        self._choice_branches: dict[str, tuple[ChoiceBranch, ...]] = {}
        self._postorder: list[str] = []
        self._validate_and_order_graph()
        self._compute_counts_and_indexes()

    def _parse_node(self, name: str, raw: Any) -> Node:
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
            width = stop - start + 1
            if width > self.limits.max_range_width:
                raise SchemaError(
                    f"range node {name!r} width {width} exceeds limit "
                    f"{self.limits.max_range_width}"
                )
            if not target:
                raise SchemaError(f"range node {name!r} requires target")
            return RangeNode(name=name, field=field, start=start, stop=stop, target=target)
        raise SchemaError(f"node {name!r} has unsupported type {kind!r}")

    @staticmethod
    def _targets(node: Node) -> tuple[str, ...]:
        if isinstance(node, TerminalNode):
            return ()
        if isinstance(node, ChoiceNode):
            return tuple(branch.target for branch in node.branches)
        return (node.target,)

    def _validate_and_order_graph(self) -> None:
        from collections import deque

        for node in self.nodes.values():
            for target in self._targets(node):
                if target not in self.nodes:
                    raise SchemaError(f"node {node.name!r} targets missing node {target!r}")

        reachable: set[str] = set()
        pending = [self.root]
        while pending:
            name = pending.pop()
            if name in reachable:
                continue
            reachable.add(name)
            pending.extend(self._targets(self.nodes[name]))

        unreachable = set(self.nodes) - reachable
        if unreachable:
            names = ", ".join(sorted(unreachable))
            raise SchemaError(f"unreachable nodes are not allowed: {names}")

        indegree = {name: 0 for name in reachable}
        for name in reachable:
            for target in self._targets(self.nodes[name]):
                indegree[target] += 1
        queue = deque(sorted(name for name, degree in indegree.items() if degree == 0))
        topological: list[str] = []
        while queue:
            name = queue.popleft()
            topological.append(name)
            for target in self._targets(self.nodes[name]):
                indegree[target] -= 1
                if indegree[target] == 0:
                    queue.append(target)
        if len(topological) != len(reachable):
            cyclic = sorted(name for name, degree in indegree.items() if degree > 0)
            raise SchemaError(f"cycle detected involving node {cyclic[0]!r}")
        self._postorder = list(reversed(topological))

    def _compute_counts_and_indexes(self) -> None:
        for name in self._postorder:
            node = self.nodes[name]
            if isinstance(node, TerminalNode):
                total = 1
                depth = 0
            elif isinstance(node, ChoiceNode):
                total = sum(self._counts[branch.target] for branch in node.branches)
                depth = 1 + max(self._depths[branch.target] for branch in node.branches)
            else:
                width = node.stop - node.start + 1
                total = width * self._counts[node.target]
                depth = 1 + self._depths[node.target]
            if total <= 0:
                raise SchemaError(f"node {name!r} has an empty domain")
            if total.bit_length() > self.limits.max_domain_bits:
                raise SchemaError(
                    f"node {name!r} domain requires {total.bit_length()} bits, exceeding "
                    f"limit {self.limits.max_domain_bits}"
                )
            if depth > self.limits.max_depth:
                raise SchemaError(
                    f"schema depth {depth} exceeds limit {self.limits.max_depth}"
                )
            self._counts[name] = total
            self._depths[name] = depth

        for name, node in self.nodes.items():
            if not isinstance(node, ChoiceNode):
                continue
            offset = 0
            lookup: dict[str, tuple[str, int]] = {}
            ends: list[int] = []
            for branch in node.branches:
                lookup[branch.value] = (branch.target, offset)
                offset += self._counts[branch.target]
                ends.append(offset)
            self._choice_lookup[name] = lookup
            self._choice_ends[name] = tuple(ends)
            self._choice_branches[name] = node.branches

    def _count(self, name: str) -> int:
        return self._counts[name]

    @property
    def count(self) -> int:
        return self._counts[self.root]

    @property
    def bit_length(self) -> int:
        return max(0, (self.count - 1).bit_length())

    @property
    def depth(self) -> int:
        return self._depths[self.root]

    @property
    def edge_count(self) -> int:
        return sum(len(self._targets(node)) for node in self.nodes.values())

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
                selected = self._choice_lookup[node_name].get(token)
                if selected is None:
                    allowed = ", ".join(branch.value for branch in node.branches)
                    raise SchemaError(
                        f"invalid value {token!r} for {node.field!r}; allowed: {allowed}"
                    )
                node_name, offset = selected
                rank += offset
            else:
                if not isinstance(token, int) or isinstance(token, bool):
                    raise SchemaError(f"field {node.field!r} requires an integer")
                if token < node.start or token > node.stop:
                    raise SchemaError(
                        f"value {token} outside {node.field!r} range {node.start}..{node.stop}"
                    )
                block = self._counts[node.target]
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
                branch_index = bisect_right(self._choice_ends[node_name], remainder)
                if branch_index >= len(node.branches):
                    raise AssertionError("internal choice unranking invariant failed")
                previous_end = 0 if branch_index == 0 else self._choice_ends[node_name][branch_index - 1]
                remainder -= previous_end
                branch = node.branches[branch_index]
                output.append(branch.value)
                node_name = branch.target
            else:
                block = self._counts[node.target]
                offset, remainder = divmod(remainder, block)
                value = node.start + offset
                if value > node.stop:
                    raise AssertionError("internal range unranking invariant failed")
                output.append(value)
                node_name = node.target

    def sample(self, rng: random.Random | None = None) -> list[Token]:
        source = rng if rng is not None else random.SystemRandom()
        return self.unrank(source.randrange(self.count))

    def enumerate_values(self, start: int = 0, stop: int | None = None) -> Iterator[list[Token]]:
        end = self.count if stop is None else stop
        if start < 0 or end < start or end > self.count:
            raise SchemaError("invalid enumeration interval")
        for index in range(start, end):
            yield self.unrank(index)

    def partition(self, worker: int, workers: int) -> tuple[int, int]:
        if workers <= 0 or worker < 0 or worker >= workers:
            raise SchemaError("worker must be in 0..workers-1 and workers must be positive")
        start = (worker * self.count) // workers
        stop = ((worker + 1) * self.count) // workers
        return start, stop

    def trace(self, value: Sequence[Token]) -> list[str]:
        tokens = list(value)
        position = 0
        node_name = self.root
        visited: list[str] = []
        while True:
            visited.append(node_name)
            node = self.nodes[node_name]
            if isinstance(node, TerminalNode):
                if position != len(tokens):
                    raise SchemaError("value contains trailing tokens after terminal state")
                return visited
            if position >= len(tokens):
                raise SchemaError(f"value ended before field {node.field!r}")
            token = tokens[position]
            position += 1
            if isinstance(node, ChoiceNode):
                if not isinstance(token, str):
                    raise SchemaError(f"field {node.field!r} requires a string choice")
                selected = self._choice_lookup[node_name].get(token)
                if selected is None:
                    raise SchemaError(f"invalid value {token!r} for {node.field!r}")
                node_name = selected[0]
            else:
                if not isinstance(token, int) or isinstance(token, bool):
                    raise SchemaError(f"field {node.field!r} requires an integer")
                if token < node.start or token > node.stop:
                    raise SchemaError(
                        f"value {token} outside {node.field!r} range {node.start}..{node.stop}"
                    )
                node_name = node.target

    def encode_rank(self, value: Sequence[Token]) -> bytes:
        width = max(1, (self.bit_length + 7) // 8)
        return self.rank(value).to_bytes(width, "big")

    def decode_rank(self, payload: bytes) -> list[Token]:
        width = max(1, (self.bit_length + 7) // 8)
        if len(payload) != width:
            raise SchemaError(f"rank payload must be exactly {width} bytes")
        return self.unrank(int.from_bytes(payload, "big"))

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "count": self.count,
            "minimum_fixed_bits": self.bit_length,
            "nodes": len(self.nodes),
            "edges": self.edge_count,
            "depth": self.depth,
            "canonical_hash": self.canonical_hash,
        }


def load_schema(
    path: str | Path,
    *,
    limits: SchemaLimits | None = None,
) -> CompiledSchema:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(document, Mapping):
        raise SchemaError("schema document must be a JSON object")
    return CompiledSchema(document, limits=limits)
