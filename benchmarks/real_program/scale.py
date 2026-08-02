from __future__ import annotations

import json
import math
from pathlib import Path
import random
import time
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from pdrs import CompiledSchema

from .common import FIGURES, PROCESSED, RAW, ensure_dirs, write_csv, write_json
from .schemas import iso20022_schema, quantlib_schema, simplefix_schema


def _replacement_stats(domain: int, budget: int, seed: int) -> dict[str, Any]:
    rng = random.Random(seed)
    started = time.perf_counter()
    ranks = [rng.randrange(domain) for _ in range(budget)]
    elapsed = time.perf_counter() - started
    unique = len(set(ranks))
    expected_unique = domain * (1.0 - ((domain - 1.0) / domain) ** budget)
    return {
        "domain": domain,
        "budget": budget,
        "unique": unique,
        "duplicates": budget - unique,
        "duplicate_rate": (budget - unique) / budget,
        "expected_duplicates": budget - expected_unique,
        "seconds": elapsed,
    }


def _worker_overlap(domain: int, workers: int, per_worker: int, seed: int) -> dict[str, Any]:
    pdrs_sets = []
    for worker in range(workers):
        start = (worker * domain) // workers
        stop = min(((worker + 1) * domain) // workers, start + per_worker)
        pdrs_sets.append(set(range(start, stop)))
    random_sets = []
    for worker in range(workers):
        rng = random.Random(seed + worker * 1009)
        random_sets.append({rng.randrange(domain) for _ in range(per_worker)})

    def summarize(sets: list[set[int]]) -> tuple[int, int, float]:
        total = sum(len(values) for values in sets)
        union = len(set().union(*sets))
        overlap = total - union
        return total, overlap, overlap / total if total else 0.0

    pdrs_total, pdrs_overlap, pdrs_rate = summarize(pdrs_sets)
    random_total, random_overlap, random_rate = summarize(random_sets)
    return {
        "workers": workers,
        "per_worker": per_worker,
        "pdrs_total_unique_within_workers": pdrs_total,
        "pdrs_cross_worker_overlap": pdrs_overlap,
        "pdrs_overlap_rate": pdrs_rate,
        "random_total_unique_within_workers": random_total,
        "random_cross_worker_overlap": random_overlap,
        "random_overlap_rate": random_rate,
    }


def run(seed: int = 20260802) -> dict[str, Any]:
    ensure_dirs()
    schemas = {
        "simplefix": CompiledSchema(simplefix_schema()),
        "quantlib": CompiledSchema(quantlib_schema()),
        "iso20022": CompiledSchema(iso20022_schema()),
    }
    budgets = [10_000, 100_000, 500_000]
    rows: list[dict[str, Any]] = []
    overlap_rows: list[dict[str, Any]] = []
    for name, schema in schemas.items():
        for budget in budgets:
            random_stats = _replacement_stats(schema.count, budget, seed + budget + schema.count)
            rows.append({
                "schema": name,
                "method": "random_with_replacement",
                **random_stats,
            })
            rows.append({
                "schema": name,
                "method": "pdrs_without_replacement",
                "domain": schema.count,
                "budget": budget,
                "unique": budget,
                "duplicates": 0,
                "duplicate_rate": 0.0,
                "expected_duplicates": 0.0,
                "seconds": 0.0,
            })
        overlap_rows.append({
            "schema": name,
            "domain": schema.count,
            **_worker_overlap(schema.count, workers=8, per_worker=50_000, seed=seed + schema.count),
        })

    write_csv(RAW / "real_program_scale_duplicates.csv", rows)
    write_csv(RAW / "real_program_scale_workers.csv", overlap_rows)

    random_rows = [row for row in rows if row["method"] == "random_with_replacement"]
    plt.figure(figsize=(10, 5.5))
    for name in schemas:
        subset = [row for row in random_rows if row["schema"] == name]
        plt.plot([row["budget"] for row in subset], [100.0 * row["duplicate_rate"] for row in subset], marker="o", label=name)
    plt.xscale("log")
    plt.xlabel("Generated rank draws")
    plt.ylabel("Duplicate draws, percent")
    plt.title("Duplicate growth in real-program domains under replacement sampling")
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIGURES / "real_program_scale_duplicates.svg", bbox_inches="tight")
    plt.savefig(FIGURES / "real_program_scale_duplicates.png", dpi=180, bbox_inches="tight")
    plt.close()

    plt.figure(figsize=(9, 5))
    positions = list(range(len(overlap_rows)))
    width = 0.35
    plt.bar([position - width / 2 for position in positions], [100.0 * row["pdrs_overlap_rate"] for row in overlap_rows], width=width, label="PDRS partitions")
    plt.bar([position + width / 2 for position in positions], [100.0 * row["random_overlap_rate"] for row in overlap_rows], width=width, label="Independent random workers")
    plt.xticks(positions, [row["schema"] for row in overlap_rows])
    plt.ylabel("Cross-worker overlap, percent")
    plt.title("Eight-worker campaigns with 50,000 unique draws per worker")
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIGURES / "real_program_scale_worker_overlap.svg", bbox_inches="tight")
    plt.savefig(FIGURES / "real_program_scale_worker_overlap.png", dpi=180, bbox_inches="tight")
    plt.close()

    summary = {
        "budgets": budgets,
        "worker_configuration": {"workers": 8, "per_worker": 50_000},
        "duplicates": rows,
        "worker_overlap": overlap_rows,
    }
    write_json(PROCESSED / "real_program_scale_summary.json", summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
