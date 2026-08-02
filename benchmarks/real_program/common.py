from __future__ import annotations

from dataclasses import dataclass
import csv
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
import time
from typing import Any, Callable, Iterable, Sequence

from pdrs import CompiledSchema
from pdrs.core import ChoiceNode, RangeNode, TerminalNode

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results" / "real_program"
RAW = RESULTS / "raw"
PROCESSED = RESULTS / "processed"
FIGURES = RESULTS / "figures"
FAILURES = RESULTS / "failures"


def ensure_dirs() -> None:
    for path in (RAW, PROCESSED, FIGURES, FAILURES):
        path.mkdir(parents=True, exist_ok=True)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"cannot write empty CSV: {path}")
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def local_uniform_sample(schema: CompiledSchema, rng: random.Random) -> list[str | int]:
    node_name = schema.root
    output: list[str | int] = []
    while True:
        node = schema.nodes[node_name]
        if isinstance(node, TerminalNode):
            return output
        if isinstance(node, ChoiceNode):
            branch = rng.choice(node.branches)
            output.append(branch.value)
            node_name = branch.target
        elif isinstance(node, RangeNode):
            output.append(rng.randint(node.start, node.stop))
            node_name = node.target
        else:
            raise AssertionError(f"unknown node type {type(node)}")


def distinct_rank_values(schema: CompiledSchema, budget: int, seed: int) -> list[list[str | int]]:
    budget = min(budget, schema.count)
    rng = random.Random(seed)
    return [schema.unrank(rank) for rank in rng.sample(range(schema.count), budget)]


def replacement_rank_values(schema: CompiledSchema, budget: int, seed: int) -> list[list[str | int]]:
    rng = random.Random(seed)
    return [schema.unrank(rng.randrange(schema.count)) for _ in range(budget)]


def local_uniform_values(schema: CompiledSchema, budget: int, seed: int) -> list[list[str | int]]:
    rng = random.Random(seed)
    return [local_uniform_sample(schema, rng) for _ in range(budget)]


def canonical_value(value: Sequence[str | int]) -> str:
    return json.dumps(list(value), separators=(",", ":"), ensure_ascii=True)


def generation_metrics(values: Sequence[Sequence[str | int]], elapsed: float) -> dict[str, Any]:
    canonical = [canonical_value(value) for value in values]
    unique = len(set(canonical))
    return {
        "generated": len(values),
        "unique": unique,
        "duplicate": len(values) - unique,
        "unique_rate": unique / len(values) if values else 0.0,
        "generation_seconds": elapsed,
        "generation_per_second": len(values) / elapsed if elapsed else math.inf,
    }


def timed_generate(generator: Callable[[], list[list[str | int]]]) -> tuple[list[list[str | int]], float]:
    started = time.perf_counter()
    values = generator()
    return values, time.perf_counter() - started


def worker_overlap(schema: CompiledSchema, workers: int, per_worker: int, seed: int) -> dict[str, float]:
    pdrs_sets: list[set[int]] = []
    for worker in range(workers):
        start = (worker * schema.count) // workers
        stop = ((worker + 1) * schema.count) // workers
        selected = set(range(start, min(stop, start + per_worker)))
        pdrs_sets.append(selected)
    rng = random.Random(seed)
    random_sets = [{rng.randrange(schema.count) for _ in range(per_worker)} for _ in range(workers)]

    def overlap_fraction(sets: list[set[int]]) -> float:
        total = sum(len(item) for item in sets)
        union = len(set().union(*sets))
        return (total - union) / total if total else 0.0

    return {
        "pdrs_overlap_fraction": overlap_fraction(pdrs_sets),
        "random_overlap_fraction": overlap_fraction(random_sets),
    }


def percentile(values: Sequence[float], p: float) -> float:
    if not values:
        return math.nan
    ordered = sorted(values)
    index = (len(ordered) - 1) * p / 100.0
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return float(ordered[lower])
    weight = index - lower
    return float(ordered[lower] * (1.0 - weight) + ordered[upper] * weight)


def summarize_numbers(values: Sequence[float]) -> dict[str, float]:
    if not values:
        return {"count": 0, "mean": math.nan, "median": math.nan, "p95": math.nan, "max": math.nan}
    return {
        "count": len(values),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "p95": percentile(values, 95),
        "max": max(values),
    }


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_checksums() -> None:
    rows: list[dict[str, str]] = []
    for directory in (RAW, PROCESSED, FIGURES, FAILURES):
        for path in sorted(directory.rglob("*")):
            if path.is_file() and path.name != "SHA256SUMS.csv":
                rows.append({"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path)})
    write_csv(PROCESSED / "SHA256SUMS.csv", rows)


@dataclass(frozen=True)
class Failure:
    evaluation: str
    rank: int | None
    oracle: str
    detail: str
    value: Sequence[str | int] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "evaluation": self.evaluation,
            "rank": self.rank,
            "oracle": self.oracle,
            "detail": self.detail,
            "value": list(self.value) if self.value is not None else None,
        }
