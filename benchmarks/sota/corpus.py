from __future__ import annotations

from dataclasses import dataclass
from functools import reduce
from operator import mul
from typing import Sequence


@dataclass(frozen=True)
class Domain:
    name: str
    branches: tuple[tuple[int, ...], ...]

    @property
    def branch_sizes(self) -> tuple[int, ...]:
        return tuple(reduce(mul, widths, 1) for widths in self.branches)

    @property
    def count(self) -> int:
        return sum(self.branch_sizes)

    @property
    def max_fields(self) -> int:
        return max(len(widths) for widths in self.branches)

    def rank(self, branch: int, values: Sequence[int]) -> int:
        widths = self.branches[branch]
        if len(values) != len(widths):
            raise ValueError("wrong number of fields")
        local = 0
        for value, width in zip(values, widths):
            if not 0 <= value < width:
                raise ValueError("field outside range")
            local = local * width + value
        return sum(self.branch_sizes[:branch]) + local

    def unrank(self, rank: int) -> tuple[int, tuple[int, ...]]:
        if not 0 <= rank < self.count:
            raise ValueError("rank outside domain")
        offset = 0
        for branch, (widths, size) in enumerate(zip(self.branches, self.branch_sizes)):
            if rank < offset + size:
                local = rank - offset
                values = [0] * len(widths)
                for index in range(len(widths) - 1, -1, -1):
                    values[index] = local % widths[index]
                    local //= widths[index]
                return branch, tuple(values)
            offset += size
        raise AssertionError("unreachable")

    def pdrs_schema(self) -> dict:
        nodes: dict[str, dict] = {"end": {"type": "terminal"}}
        branches = []
        for branch_index, widths in enumerate(self.branches):
            target = f"b{branch_index}_f0" if widths else "end"
            branches.append({"value": f"b{branch_index}", "target": target})
            for field_index, width in enumerate(widths):
                next_target = (
                    f"b{branch_index}_f{field_index + 1}"
                    if field_index + 1 < len(widths)
                    else "end"
                )
                nodes[f"b{branch_index}_f{field_index}"] = {
                    "type": "range",
                    "field": f"field_{field_index}",
                    "start": 0,
                    "stop": width - 1,
                    "target": next_target,
                }
        nodes["root"] = {
            "type": "choice",
            "field": "branch",
            "branches": branches,
        }
        return {"name": self.name, "version": "sota-1", "root": "root", "nodes": nodes}

    def branch_of_rank(self, rank: int) -> int:
        return self.unrank(rank)[0]

    def boundaries(self) -> set[int]:
        result: set[int] = set()
        offset = 0
        for widths, size in zip(self.branches, self.branch_sizes):
            result.add(offset)
            result.add(offset + size - 1)
            stride = size
            for width in widths:
                stride //= width
                if stride:
                    for k in range(1, min(width, 8)):
                        point = offset + k * stride
                        if point < offset + size:
                            result.add(point)
                            result.add(point - 1)
            offset += size
        return {rank for rank in result if 0 <= rank < self.count}


DOMAINS: tuple[Domain, ...] = (
    Domain("balanced_product", ((8, 8, 8),)),
    Domain("imbalanced_choice", ((2,), (4, 4), (16, 16), (16, 16, 8))),
    Domain("dependent_record", ((4, 8), (8, 8, 4), (2, 2, 2, 2, 2, 2), (16,))),
    Domain("protocol_message", ((16,), (8, 16, 8), (4, 16), (2, 4))),
    Domain("action_space", ((16, 4), (8, 8, 4), (16, 16), (2, 2, 2))),
)

BY_NAME = {domain.name: domain for domain in DOMAINS}


def parse_line(domain: Domain, text: str) -> int:
    parts = text.strip().split(",")
    if not parts or not parts[0].startswith("b"):
        raise ValueError(f"invalid generated object: {text!r}")
    branch = int(parts[0][1:])
    values = tuple(int(part) for part in parts[1:] if part != "")
    return domain.rank(branch, values)
