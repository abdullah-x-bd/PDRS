from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from math import gcd
import hashlib
import json
import random
import unicodedata
from typing import Any, Iterator, Mapping, Sequence

Token = str | int


class SchemaError(ValueError):
    pass


@dataclass(frozen=True)
class Limits:
    max_nodes: int = 100_000
    max_depth: int = 10_000
    max_range_width: int = 10**12
    max_domain_bits: int = 1_000_000


@dataclass(frozen=True)
class Terminal:
    name: str


@dataclass(frozen=True)
class Branch:
    value: str
    target: str


@dataclass(frozen=True)
class Choice:
    name: str
    field: str
    branches: tuple[Branch, ...]


@dataclass(frozen=True)
class Range:
    name: str
    field: str
    start: int
    stop: int
    target: str


Node = Terminal | Choice | Range


def _nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def _canonicalize(value: Any) -> Any:
    if isinstance(value, str):
        return _nfc(value)
    if isinstance(value, list):
        return [_canonicalize(item) for item in value]
    if isinstance(value, Mapping):
        return {
            _nfc(str(key)): _canonicalize(item)
            for key, item in sorted(value.items(), key=lambda pair: _nfc(str(pair[0])))
        }
    return value


class CompiledSchema:
    """Finite acyclic dependent domain with typed injective record lowering."""

    def __init__(self, document: Mapping[str, Any], *, limits: Limits | None = None):
        self.limits = limits or Limits()
        canonical = _canonicalize(document)
        self.document = json.loads(json.dumps(canonical, ensure_ascii=False))
        payload = json.dumps(self.document, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        self._hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        self.name = str(canonical.get("name", "unnamed"))
        self.version = str(canonical.get("version", "0"))
        self.root = str(canonical.get("root", ""))
        raw_nodes = canonical.get("nodes")
        if not self.root:
            raise SchemaError("schema root is required")
        if not isinstance(raw_nodes, Mapping) or not raw_nodes:
            raise SchemaError("schema nodes must be a non-empty mapping")
        if len(raw_nodes) > self.limits.max_nodes:
            raise SchemaError("node limit exceeded")
        self.nodes = {str(name): self._parse_node(str(name), raw) for name, raw in raw_nodes.items()}
        if self.root not in self.nodes:
            raise SchemaError("root target is missing")
        self._counts: dict[str, int] = {}
        self._depths: dict[str, int] = {}
        self._choice_ends: dict[str, tuple[int, ...]] = {}
        self._choice_lookup: dict[str, dict[str, tuple[str, int]]] = {}
        self._postorder: list[str] = []
        self._validate_graph()
        self._validate_path_fields()
        self._compile()

    def _parse_node(self, name: str, raw: Any) -> Node:
        if not isinstance(raw, Mapping):
            raise SchemaError(f"node {name!r} must be an object")
        kind = raw.get("type")
        if kind == "terminal":
            return Terminal(name)
        if kind == "choice":
            items = raw.get("branches")
            if not isinstance(items, list) or not items:
                raise SchemaError("choice requires a non-empty branch list")
            branches: list[Branch] = []
            seen: set[str] = set()
            for item in items:
                if not isinstance(item, Mapping) or not isinstance(item.get("value"), str):
                    raise SchemaError("choice branches require string labels")
                value = _nfc(item["value"])
                target = str(item.get("target", ""))
                if not value or not target:
                    raise SchemaError("branch requires value and target")
                if value in seen:
                    raise SchemaError(f"duplicate normalized label {value!r}")
                seen.add(value)
                branches.append(Branch(value, target))
            return Choice(name, _nfc(str(raw.get("field", name))), tuple(branches))
        if kind == "range":
            start, stop = raw.get("start"), raw.get("stop")
            if not isinstance(start, int) or isinstance(start, bool):
                raise SchemaError("range start must be a typed integer")
            if not isinstance(stop, int) or isinstance(stop, bool):
                raise SchemaError("range stop must be a typed integer")
            if stop < start:
                raise SchemaError("range is empty")
            if stop - start + 1 > self.limits.max_range_width:
                raise SchemaError("range width limit exceeded")
            target = str(raw.get("target", ""))
            if not target:
                raise SchemaError("range target is required")
            return Range(name, _nfc(str(raw.get("field", name))), start, stop, target)
        raise SchemaError(f"unsupported node type {kind!r}")

    @staticmethod
    def _targets(node: Node) -> tuple[str, ...]:
        if isinstance(node, Terminal):
            return ()
        if isinstance(node, Choice):
            return tuple(branch.target for branch in node.branches)
        return (node.target,)

    def _validate_graph(self) -> None:
        from collections import deque

        for node in self.nodes.values():
            for target in self._targets(node):
                if target not in self.nodes:
                    raise SchemaError(f"missing target {target!r}")
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
            raise SchemaError(f"unreachable nodes: {sorted(unreachable)}")
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
            raise SchemaError("cycle detected")
        self._postorder = list(reversed(topological))

    def _validate_path_fields(self) -> None:
        pending: list[tuple[str, frozenset[str]]] = [(self.root, frozenset())]
        visited: set[tuple[str, frozenset[str]]] = set()
        while pending:
            name, used = pending.pop()
            state = (name, used)
            if state in visited:
                continue
            visited.add(state)
            node = self.nodes[name]
            if isinstance(node, Terminal):
                continue
            if node.field in used:
                raise SchemaError(f"field {node.field!r} repeats on one root-to-terminal path")
            next_used = frozenset(set(used) | {node.field})
            pending.extend((target, next_used) for target in self._targets(node))

    def _compile(self) -> None:
        for name in self._postorder:
            node = self.nodes[name]
            if isinstance(node, Terminal):
                count, depth = 1, 0
            elif isinstance(node, Choice):
                count = sum(self._counts[branch.target] for branch in node.branches)
                depth = 1 + max(self._depths[branch.target] for branch in node.branches)
            else:
                count = (node.stop - node.start + 1) * self._counts[node.target]
                depth = 1 + self._depths[node.target]
            if count.bit_length() > self.limits.max_domain_bits:
                raise SchemaError("domain bit-length limit exceeded")
            if depth > self.limits.max_depth:
                raise SchemaError("depth limit exceeded")
            self._counts[name], self._depths[name] = count, depth
        for name, node in self.nodes.items():
            if not isinstance(node, Choice):
                continue
            ends: list[int] = []
            lookup: dict[str, tuple[str, int]] = {}
            offset = 0
            for branch in node.branches:
                lookup[branch.value] = (branch.target, offset)
                offset += self._counts[branch.target]
                ends.append(offset)
            self._choice_ends[name] = tuple(ends)
            self._choice_lookup[name] = lookup

    @property
    def count(self) -> int:
        return self._counts[self.root]

    @property
    def depth(self) -> int:
        return self._depths[self.root]

    @property
    def bit_length(self) -> int:
        return max(0, (self.count - 1).bit_length())

    @property
    def canonical_hash(self) -> str:
        return self._hash

    def rank(self, tokens: Sequence[Token]) -> int:
        items, position, rank, name = list(tokens), 0, 0, self.root
        while True:
            node = self.nodes[name]
            if isinstance(node, Terminal):
                if position != len(items):
                    raise SchemaError("trailing tokens")
                return rank
            if position >= len(items):
                raise SchemaError("token sequence ended early")
            token = items[position]
            position += 1
            if isinstance(node, Choice):
                if not isinstance(token, str):
                    raise SchemaError("choice token must be a string")
                selected = self._choice_lookup[name].get(_nfc(token))
                if selected is None:
                    raise SchemaError("invalid choice token")
                name, offset = selected
                rank += offset
            else:
                if not isinstance(token, int) or isinstance(token, bool):
                    raise SchemaError("range token must be a typed integer")
                if token < node.start or token > node.stop:
                    raise SchemaError("range token outside bounds")
                rank += (token - node.start) * self._counts[node.target]
                name = node.target

    def unrank(self, index: int) -> list[Token]:
        if not isinstance(index, int) or isinstance(index, bool) or index < 0 or index >= self.count:
            raise SchemaError("rank outside domain")
        output: list[Token] = []
        name, remainder = self.root, index
        while True:
            node = self.nodes[name]
            if isinstance(node, Terminal):
                if remainder != 0:
                    raise AssertionError("nonzero terminal remainder")
                return output
            if isinstance(node, Choice):
                branch_index = bisect_right(self._choice_ends[name], remainder)
                previous = 0 if branch_index == 0 else self._choice_ends[name][branch_index - 1]
                remainder -= previous
                branch = node.branches[branch_index]
                output.append(branch.value)
                name = branch.target
            else:
                block = self._counts[node.target]
                offset, remainder = divmod(remainder, block)
                output.append(node.start + offset)
                name = node.target

    def lower(self, tokens: Sequence[Token]) -> dict[str, dict[str, Any]]:
        items, position, name = list(tokens), 0, self.root
        record: dict[str, dict[str, Any]] = {}
        while True:
            node = self.nodes[name]
            if isinstance(node, Terminal):
                if position != len(items):
                    raise SchemaError("trailing tokens")
                return record
            if position >= len(items):
                raise SchemaError("token sequence ended early")
            token = items[position]
            position += 1
            if isinstance(node, Choice):
                if not isinstance(token, str):
                    raise SchemaError("choice token must be a string")
                token = _nfc(token)
                selected = self._choice_lookup[name].get(token)
                if selected is None:
                    raise SchemaError("invalid choice")
                record[node.field] = {"type": "string", "value": token}
                name = selected[0]
            else:
                if not isinstance(token, int) or isinstance(token, bool):
                    raise SchemaError("range token must be an integer")
                if token < node.start or token > node.stop:
                    raise SchemaError("range token outside bounds")
                record[node.field] = {"type": "integer", "value": token}
                name = node.target

    def enumerate(self, start: int = 0, stop: int | None = None) -> Iterator[list[Token]]:
        end = self.count if stop is None else stop
        if start < 0 or end < start or end > self.count:
            raise SchemaError("invalid interval")
        for rank in range(start, end):
            yield self.unrank(rank)

    def sample_without_replacement(self, budget: int, rng: random.Random) -> list[int]:
        """Floyd's O(B)-space uniform subset algorithm."""
        if budget < 0 or budget > self.count:
            raise SchemaError("budget must lie in 0..N")
        selected: set[int] = set()
        for j in range(self.count - budget, self.count):
            candidate = rng.randrange(j + 1)
            selected.add(j if candidate in selected else candidate)
        result = list(selected)
        rng.shuffle(result)
        return result

    def contiguous_partitions(self, workers: int) -> list[list[int]]:
        return [list(range((w * self.count) // workers, ((w + 1) * self.count) // workers)) for w in range(workers)]

    def strided_partitions(self, workers: int) -> list[list[int]]:
        return [list(range(w, self.count, workers)) for w in range(workers)]

    def affine_permutation(self, seed: int) -> tuple[int, int]:
        rng = random.Random(seed)
        multiplier = rng.randrange(1, max(2, self.count))
        while gcd(multiplier, self.count) != 1:
            multiplier = (multiplier + 1) % self.count or 1
        return multiplier, rng.randrange(self.count)

    def permuted_partitions(self, workers: int, seed: int) -> list[list[int]]:
        multiplier, offset = self.affine_permutation(seed)
        return [[(multiplier * rank + offset) % self.count for rank in part] for part in self.contiguous_partitions(workers)]

    def hash_partitions(self, workers: int, seed: int) -> list[list[int]]:
        output = [[] for _ in range(workers)]
        key = seed.to_bytes(8, "big")
        width = max(1, (self.bit_length + 7) // 8)
        for rank in range(self.count):
            digest = hashlib.blake2b(rank.to_bytes(width, "big"), key=key, digest_size=8).digest()
            output[int.from_bytes(digest, "big") % workers].append(rank)
        return output


def naive_enumerate(document: Mapping[str, Any]) -> list[list[Token]]:
    nodes = document["nodes"]

    def walk(name: str) -> list[list[Token]]:
        node = nodes[name]
        if node["type"] == "terminal":
            return [[]]
        output: list[list[Token]] = []
        if node["type"] == "choice":
            for branch in node["branches"]:
                output.extend([[branch["value"], *tail] for tail in walk(branch["target"])])
        else:
            for value in range(node["start"], node["stop"] + 1):
                output.extend([[value, *tail] for tail in walk(node["target"])])
        return output

    return walk(document["root"])


def branch_intervals(schema: CompiledSchema) -> list[tuple[str, int, int]]:
    root = schema.nodes[schema.root]
    if not isinstance(root, Choice):
        return [("root", 0, schema.count)]
    output: list[tuple[str, int, int]] = []
    start = 0
    for branch in root.branches:
        stop = start + schema._counts[branch.target]
        output.append((branch.value, start, stop))
        start = stop
    return output
