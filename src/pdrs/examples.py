from __future__ import annotations

from typing import Any


def fixed_radix_schema(name: str, radices: list[int]) -> dict[str, Any]:
    """Build a fixed mixed-radix schema for tests and benchmarks."""
    if not radices or any(radix <= 0 for radix in radices):
        raise ValueError("radices must be positive")
    nodes: dict[str, Any] = {"end": {"type": "terminal"}}
    target = "end"
    for index in reversed(range(len(radices))):
        node_name = f"digit_{index}"
        nodes[node_name] = {
            "type": "range",
            "field": node_name,
            "start": 0,
            "stop": radices[index] - 1,
            "target": target,
        }
        target = node_name
    return {"name": name, "version": "1", "root": target, "nodes": nodes}
