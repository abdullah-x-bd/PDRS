from __future__ import annotations

import calendar
import random
from typing import Any


def fixed_radix_schema(name: str, radices: list[int]) -> dict[str, Any]:
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


def calendar_schema(start_year: int, end_year: int) -> dict[str, Any]:
    if end_year < start_year:
        raise ValueError("end year must not precede start year")
    nodes: dict[str, Any] = {"end": {"type": "terminal"}}
    year_branches: list[dict[str, str]] = []
    for year in range(start_year, end_year + 1):
        month_node = f"months_{year}"
        year_branches.append({"value": str(year), "target": month_node})
        month_branches: list[dict[str, str]] = []
        for month in range(1, 13):
            day_node = f"days_{year}_{month}"
            month_branches.append({"value": f"{month:02d}", "target": day_node})
            days = calendar.monthrange(year, month)[1]
            nodes[day_node] = {
                "type": "range",
                "field": "day",
                "start": 1,
                "stop": days,
                "target": "end",
            }
        nodes[month_node] = {
            "type": "choice",
            "field": "month",
            "branches": month_branches,
        }
    nodes["year"] = {
        "type": "choice",
        "field": "year",
        "branches": year_branches,
    }
    return {
        "name": f"calendar-{start_year}-{end_year}",
        "version": "1",
        "root": "year",
        "nodes": nodes,
    }


def layered_dag_schema(
    name: str,
    *,
    depth: int,
    branch_factor: int,
    range_width: int = 1,
) -> dict[str, Any]:
    """Compact DAG with exponentially large domain and linear node count."""
    if depth <= 0 or branch_factor <= 0 or range_width <= 0:
        raise ValueError("parameters must be positive")
    nodes: dict[str, Any] = {"end": {"type": "terminal"}}
    target = "end"
    for level in reversed(range(depth)):
        if range_width > 1:
            range_name = f"range_{level}"
            nodes[range_name] = {
                "type": "range",
                "field": f"r{level}",
                "start": 0,
                "stop": range_width - 1,
                "target": target,
            }
            target_for_choice = range_name
        else:
            target_for_choice = target
        choice_name = f"choice_{level}"
        nodes[choice_name] = {
            "type": "choice",
            "field": f"c{level}",
            "branches": [
                {"value": f"b{branch}", "target": target_for_choice}
                for branch in range(branch_factor)
            ],
        }
        target = choice_name
    return {"name": name, "version": "1", "root": target, "nodes": nodes}


def imbalanced_schema(name: str, branch_sizes: list[int]) -> dict[str, Any]:
    if not branch_sizes or any(size <= 0 for size in branch_sizes):
        raise ValueError("branch sizes must be positive")
    nodes: dict[str, Any] = {"end": {"type": "terminal"}}
    branches: list[dict[str, str]] = []
    for index, size in enumerate(branch_sizes):
        node = f"branch_{index}_value"
        nodes[node] = {
            "type": "range",
            "field": "value",
            "start": 0,
            "stop": size - 1,
            "target": "end",
        }
        branches.append({"value": f"branch_{index}", "target": node})
    nodes["root"] = {"type": "choice", "field": "branch", "branches": branches}
    return {"name": name, "version": "1", "root": "root", "nodes": nodes}


def random_tree_schema(
    seed: int,
    *,
    max_depth: int = 4,
    max_branches: int = 4,
    max_range: int = 6,
    terminal_probability: float = 0.2,
) -> dict[str, Any]:
    """Generate a finite explicit tree for exhaustive theorem checking."""
    rng = random.Random(seed)
    nodes: dict[str, Any] = {}
    counter = 0

    def new_name(prefix: str) -> str:
        nonlocal counter
        counter += 1
        return f"{prefix}_{counter}"

    def build(depth: int) -> str:
        if depth >= max_depth or (depth > 0 and rng.random() < terminal_probability):
            name = new_name("end")
            nodes[name] = {"type": "terminal"}
            return name
        if rng.random() < 0.55:
            name = new_name("choice")
            count = rng.randint(2, max_branches)
            branches = []
            for branch in range(count):
                target = build(depth + 1)
                branches.append({"value": f"v{depth}_{branch}", "target": target})
            nodes[name] = {
                "type": "choice",
                "field": f"choice_{depth}",
                "branches": branches,
            }
            return name
        name = new_name("range")
        width = rng.randint(1, max_range)
        target = build(depth + 1)
        nodes[name] = {
            "type": "range",
            "field": f"range_{depth}",
            "start": 0,
            "stop": width - 1,
            "target": target,
        }
        return name

    root = build(0)
    return {
        "name": f"random-tree-{seed}",
        "version": "1",
        "root": root,
        "nodes": nodes,
    }


def explicit_balanced_tree_schema(name: str, depth: int, branch_factor: int) -> dict[str, Any]:
    """Materialize a full tree to stress node growth."""
    if depth < 0 or branch_factor <= 0:
        raise ValueError("invalid tree parameters")
    nodes: dict[str, Any] = {}
    counter = 0

    def build(level: int) -> str:
        nonlocal counter
        counter += 1
        name_here = f"n{counter}"
        if level == depth:
            nodes[name_here] = {"type": "terminal"}
            return name_here
        branches = []
        for branch in range(branch_factor):
            target = build(level + 1)
            branches.append({"value": f"b{level}_{branch}", "target": target})
        nodes[name_here] = {
            "type": "choice",
            "field": f"level_{level}",
            "branches": branches,
        }
        return name_here

    root = build(0)
    return {"name": name, "version": "1", "root": root, "nodes": nodes}
