from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class MDDNode:
    label: str
    edges: tuple[tuple[Any, int], ...]


@dataclass
class ReducedMDD:
    """Exact reduced multivalued decision diagram baseline.

    This baseline represents the knowledge-compilation family. It is not KUS,
    d-DNNF, or an external knowledge compiler.
    """

    nodes: list[MDDNode]
    root: int
    counts: list[int]

    @classmethod
    def from_schema(cls, document: Mapping[str, Any]) -> "ReducedMDD":
        raw = document["nodes"]
        memo: dict[str, int] = {}
        unique: dict[tuple[str, tuple[tuple[Any, int], ...]], int] = {}
        nodes: list[MDDNode] = []
        counts: list[int] = []

        def compile_node(name: str) -> int:
            if name in memo:
                return memo[name]
            node = raw[name]
            if node["type"] == "terminal":
                key = ("terminal", ())
                count = 1
            elif node["type"] == "choice":
                edges = tuple((branch["value"], compile_node(branch["target"])) for branch in node["branches"])
                key = (str(node.get("field", name)), edges)
                count = sum(counts[target] for _, target in edges)
            else:
                target = compile_node(node["target"])
                edges = tuple((value, target) for value in range(node["start"], node["stop"] + 1))
                key = (str(node.get("field", name)), edges)
                count = len(edges) * counts[target]
            if key in unique:
                index = unique[key]
            else:
                index = len(nodes)
                unique[key] = index
                nodes.append(MDDNode(key[0], key[1]))
                counts.append(count)
            memo[name] = index
            return index

        root = compile_node(document["root"])
        return cls(nodes, root, counts)

    @property
    def count(self) -> int:
        return self.counts[self.root]
