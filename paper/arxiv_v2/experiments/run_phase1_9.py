from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
import sys
import time
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from mdd_baseline import ReducedMDD
from pdrs_v2 import CompiledSchema, SchemaError, branch_intervals, naive_enumerate

RAW = ROOT / "results" / "raw"
PROCESSED = ROOT / "results" / "processed"
FIGURES = ROOT / "figures"
for path in (RAW, PROCESSED, FIGURES, ROOT / "reproducibility"):
    path.mkdir(parents=True, exist_ok=True)

SEED = 20260803
_FEATURE_CACHE: dict[tuple[str, int], set[str]] = {}
_TOKEN_CACHE: dict[tuple[str, int], list[Any]] = {}


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def benchmark_schema() -> dict[str, Any]:
    return {
        "name": "defect-benchmark", "version": "2", "root": "kind",
        "nodes": {
            "kind": {"type": "choice", "field": "kind", "branches": [
                {"value": "A", "target": "A_x"}, {"value": "B", "target": "B_x"},
                {"value": "C", "target": "C_x"}, {"value": "D", "target": "D_x"},
            ]},
            "A_x": {"type": "range", "field": "x", "start": 0, "stop": 127, "target": "A_y"},
            "A_y": {"type": "range", "field": "y", "start": 0, "stop": 63, "target": "end"},
            "B_x": {"type": "range", "field": "x", "start": 0, "stop": 63, "target": "B_y"},
            "B_y": {"type": "range", "field": "y", "start": 0, "stop": 63, "target": "end"},
            "C_x": {"type": "range", "field": "x", "start": 0, "stop": 31, "target": "C_y"},
            "C_y": {"type": "range", "field": "y", "start": 0, "stop": 63, "target": "end"},
            "D_x": {"type": "range", "field": "x", "start": 0, "stop": 31, "target": "D_y"},
            "D_y": {"type": "range", "field": "y", "start": 0, "stop": 63, "target": "end"},
            "end": {"type": "terminal"},
        },
    }


def chain_schema(depth: int) -> dict[str, Any]:
    nodes: dict[str, Any] = {"end": {"type": "terminal"}}
    target = "end"
    for index in reversed(range(depth)):
        name = f"n{index}"
        nodes[name] = {"type": "range", "field": f"f{index}", "start": 0, "stop": 1, "target": target}
        target = name
    return {"name": f"chain-{depth}", "version": "1", "root": "n0", "nodes": nodes}


def random_tree_schema(rng: random.Random, index: int) -> dict[str, Any]:
    nodes: dict[str, Any] = {"end": {"type": "terminal"}}
    counter = 0

    def build(depth: int, path: str) -> str:
        nonlocal counter
        if depth == 0 or counter > 30:
            return "end"
        name = f"n{counter}"
        counter += 1
        if rng.random() < 0.45:
            target = build(depth - 1, path + "r")
            nodes[name] = {"type": "range", "field": f"f_{path}_{name}", "start": 0, "stop": rng.randint(1, 3), "target": target}
        else:
            branches = []
            for branch in range(rng.randint(2, 3)):
                branches.append({"value": f"v{branch}", "target": build(depth - 1, path + str(branch))})
            nodes[name] = {"type": "choice", "field": f"f_{path}_{name}", "branches": branches}
        return name

    root = build(rng.randint(1, 4), "r")
    reachable: set[str] = set()
    pending = [root]
    while pending:
        name = pending.pop()
        if name in reachable:
            continue
        reachable.add(name)
        node = nodes[name]
        if node["type"] == "choice":
            pending.extend(branch["target"] for branch in node["branches"])
        elif node["type"] == "range":
            pending.append(node["target"])
    return {"name": f"generated-{index}", "version": "1", "root": root, "nodes": {name: nodes[name] for name in reachable}}


def semantic_experiment() -> dict[str, Any]:
    rng = random.Random(SEED)
    checked = 0
    for index in range(150):
        document = random_tree_schema(rng, index)
        schema = CompiledSchema(document)
        values = naive_enumerate(document)
        assert schema.count == len(values)
        lowered: set[str] = set()
        for rank, value in enumerate(values):
            assert schema.rank(value) == rank
            assert schema.unrank(rank) == value
            lowered.add(json.dumps(schema.lower(value), sort_keys=True, ensure_ascii=False))
            checked += 1
        assert len(lowered) == len(values)

    base = benchmark_schema()
    composed = json.loads(json.dumps(base))
    decomposed = json.loads(json.dumps(base))
    composed["nodes"]["kind"]["branches"][0]["value"] = "é"
    decomposed["nodes"]["kind"]["branches"][0]["value"] = "e\u0301"
    unicode_same = CompiledSchema(composed).canonical_hash == CompiledSchema(decomposed).canonical_hash

    malformed = [
        {"name": "cycle", "root": "a", "nodes": {"a": {"type": "range", "field": "x", "start": 0, "stop": 1, "target": "a"}}},
        {"name": "dup", "root": "a", "nodes": {"a": {"type": "choice", "field": "x", "branches": [{"value": "q", "target": "e"}, {"value": "q", "target": "e"}]}, "e": {"type": "terminal"}}},
        {"name": "missing", "root": "a", "nodes": {"a": {"type": "range", "field": "x", "start": 0, "stop": 1, "target": "missing"}}},
        {"name": "unreachable", "root": "e", "nodes": {"e": {"type": "terminal"}, "x": {"type": "terminal"}}},
        {"name": "repeat", "root": "a", "nodes": {"a": {"type": "range", "field": "x", "start": 0, "stop": 1, "target": "b"}, "b": {"type": "range", "field": "x", "start": 0, "stop": 1, "target": "e"}, "e": {"type": "terminal"}}},
        {"name": "bool", "root": "a", "nodes": {"a": {"type": "range", "field": "x", "start": False, "stop": 1, "target": "e"}, "e": {"type": "terminal"}}},
        {"name": "empty", "root": "a", "nodes": {"a": {"type": "range", "field": "x", "start": 2, "stop": 1, "target": "e"}, "e": {"type": "terminal"}}},
    ]
    rejected = 0
    for document in malformed:
        try:
            CompiledSchema(document)
        except SchemaError:
            rejected += 1
    result = {
        "generated_schemas": 150, "exhaustive_objects_checked": checked,
        "round_trip_failures": 0, "lowering_collisions": 0,
        "malformed_cases": len(malformed), "malformed_rejected": rejected,
        "unicode_canonicalization_same_hash": unicode_same,
    }
    write_json(PROCESSED / "semantic_correctness.json", result)
    return result


def scalability_experiment() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    compile_rows: list[dict[str, Any]] = []
    latency_rows: list[dict[str, Any]] = []
    for depth in [2, 4, 8, 16, 32, 64, 128, 256]:
        document = chain_schema(depth)
        compile_times = []
        for _ in range(7):
            start = time.perf_counter_ns()
            schema = CompiledSchema(document)
            compile_times.append(time.perf_counter_ns() - start)
        compile_rows.append({"family": "binary_chain", "depth": depth, "nodes": len(schema.nodes), "domain_bits": schema.count.bit_length(), "compile_us_median": statistics.median(compile_times) / 1000})
        rng = random.Random(SEED + depth)
        ranks = [rng.randrange(schema.count) for _ in range(2000)]
        start = time.perf_counter_ns()
        values = [schema.unrank(rank) for rank in ranks]
        unrank_ns = time.perf_counter_ns() - start
        start = time.perf_counter_ns()
        reranked = [schema.rank(value) for value in values]
        rank_ns = time.perf_counter_ns() - start
        assert ranks == reranked
        latency_rows.append({"depth": depth, "domain_bits": schema.count.bit_length(), "rank_ns_per_object": rank_ns / len(ranks), "unrank_ns_per_object": unrank_ns / len(ranks)})

    for branches in [4, 8, 16, 32, 64]:
        shared_nodes: dict[str, Any] = {
            "root": {"type": "choice", "field": "kind", "branches": []},
            "x": {"type": "range", "field": "x", "start": 0, "stop": 31, "target": "y"},
            "y": {"type": "range", "field": "y", "start": 0, "stop": 31, "target": "end"},
            "end": {"type": "terminal"},
        }
        for index in range(branches):
            shared_nodes["root"]["branches"].append({"value": f"b{index}", "target": "x"})
        expanded_nodes: dict[str, Any] = {"root": {"type": "choice", "field": "kind", "branches": []}, "end": {"type": "terminal"}}
        for index in range(branches):
            expanded_nodes["root"]["branches"].append({"value": f"b{index}", "target": f"x{index}"})
            expanded_nodes[f"x{index}"] = {"type": "range", "field": "x", "start": 0, "stop": 31, "target": f"y{index}"}
            expanded_nodes[f"y{index}"] = {"type": "range", "field": "y", "start": 0, "stop": 31, "target": "end"}
        for family, document in [("shared_dag", {"name": "shared", "root": "root", "nodes": shared_nodes}), ("expanded_tree", {"name": "expanded", "root": "root", "nodes": expanded_nodes})]:
            start = time.perf_counter_ns(); schema = CompiledSchema(document); pdrs_us = (time.perf_counter_ns() - start) / 1000
            start = time.perf_counter_ns(); mdd = ReducedMDD.from_schema(document); mdd_us = (time.perf_counter_ns() - start) / 1000
            assert schema.count == mdd.count
            compile_rows.append({"family": family, "branches": branches, "nodes": len(schema.nodes), "mdd_nodes": len(mdd.nodes), "domain_bits": schema.count.bit_length(), "compile_us_median": pdrs_us, "mdd_compile_us": mdd_us})
    write_csv(RAW / "compilation_scalability.csv", compile_rows)
    write_csv(RAW / "rank_unrank_scalability.csv", latency_rows)
    return compile_rows, latency_rows


def tokens(schema: CompiledSchema, rank: int) -> list[Any]:
    key = (schema.canonical_hash, rank)
    if key not in _TOKEN_CACHE:
        _TOKEN_CACHE[key] = schema.unrank(rank)
    return _TOKEN_CACHE[key]


def features(schema: CompiledSchema, rank: int) -> set[str]:
    key = (schema.canonical_hash, rank)
    if key in _FEATURE_CACHE:
        return _FEATURE_CACHE[key]
    kind, x, y = tokens(schema, rank)
    result = {f"kind={kind}", f"x_bucket={int(x)//8}", f"y_bucket={int(y)//8}", f"pair={kind}:{int(x)%4}:{int(y)%4}"}
    if int(x) in {0, 31, 63, 127}:
        result.add("x_boundary")
    if int(y) in {0, 63}:
        result.add("y_boundary")
    _FEATURE_CACHE[key] = result
    return result


def defects(schema: CompiledSchema, seed: int) -> dict[str, set[int]]:
    rng = random.Random(seed)
    ranks = list(range(schema.count))
    intervals = branch_intervals(schema)
    boundary = [rank for rank in ranks if "x_boundary" in features(schema, rank) or "y_boundary" in features(schema, rank)]
    pairwise = [rank for rank in ranks if int(tokens(schema, rank)[1]) % 13 == 3 and int(tokens(schema, rank)[2]) % 11 == 7]
    execution = [rank for rank in ranks if int(hashlib.blake2s(json.dumps(tokens(schema, rank)).encode(), digest_size=2).hexdigest(), 16) % 173 == 0]
    historical: set[int] = set()
    for _, start, stop in intervals:
        historical.update({start, min(stop - 1, start + 1), stop - 1, max(start, stop - 2), (start + stop) // 2})
    historical.update(rank for rank in boundary if rank % 257 == 0)
    clustered = set()
    for center in [1300, 9200, 15100]:
        clustered.update(range(center, min(schema.count, center + 32)))
    return {
        "object_uniform": set(rng.sample(ranks, 96)),
        "branch_uniform": set().union(*(set(rng.sample(list(range(start, stop)), 24)) for _, start, stop in intervals)),
        "rare_branch": set(rng.sample(list(range(intervals[-1][1], intervals[-1][2])), 96)),
        "boundary": set(rng.sample(boundary, min(96, len(boundary)))),
        "pairwise_interaction": set(rng.sample(pairwise, min(96, len(pairwise)))),
        "clustered_local": clustered,
        "execution_derived": set(rng.sample(execution, min(96, len(execution)))),
        "historical_like_edges": set(sorted(historical)[:96]),
    }


def method_sequence(schema: CompiledSchema, method: str, budget: int, seed: int) -> list[int]:
    rng = random.Random(seed)
    intervals = branch_intervals(schema)
    if method == "pdrs_no_replacement":
        return schema.sample_without_replacement(budget, rng)
    if method == "replacement":
        return [rng.randrange(schema.count) for _ in range(budget)]
    if method == "branch_uniform":
        base, extra = divmod(budget, len(intervals))
        output = []
        for index, (_, start, stop) in enumerate(intervals):
            output.extend(rng.sample(list(range(start, stop)), base + int(index < extra)))
        rng.shuffle(output)
        return output
    boundary = [rank for rank in range(schema.count) if "x_boundary" in features(schema, rank) or "y_boundary" in features(schema, rank)]
    if method == "boundary_biased":
        selected = set(rng.sample(boundary, min(len(boundary), budget // 2)))
        for rank in schema.sample_without_replacement(budget, rng):
            if len(selected) == budget:
                break
            selected.add(rank)
        output = list(selected)
        rng.shuffle(output)
        return output
    if method == "coverage_guided":
        candidates = schema.sample_without_replacement(min(schema.count, budget * 3), rng)
        covered: set[str] = set()
        output: list[int] = []
        while candidates and len(output) < budget:
            width = min(64, len(candidates))
            local = candidates[:width]
            best_index = max(range(width), key=lambda index: len(features(schema, local[index]) - covered))
            rank = candidates.pop(best_index)
            output.append(rank)
            covered.update(features(schema, rank))
        return output
    raise ValueError(method)


def simulated_cost(schema: CompiledSchema, rank: int) -> float:
    kind, x, y = tokens(schema, rank)
    branch = {"A": 1.0, "B": 2.5, "C": 6.0, "D": 14.0}[str(kind)]
    boundary = 8.0 if int(x) in {0, 31, 63, 127} or int(y) in {0, 63} else 0.0
    numerical = 3.0 if (int(x) * int(y)) % 37 == 0 else 0.0
    return 1.0 + branch + boundary + numerical


def defect_experiment() -> list[dict[str, Any]]:
    schema = CompiledSchema(benchmark_schema())
    methods = ["pdrs_no_replacement", "replacement", "branch_uniform", "boundary_biased", "coverage_guided"]
    budgets = [100, 500, 1000]
    rows: list[dict[str, Any]] = []
    for repetition in range(30):
        defect_sets = defects(schema, SEED + 10_000 + repetition)
        for method_index, method in enumerate(methods):
            full = method_sequence(schema, method, max(budgets), SEED + 100_000 + repetition * 97 + method_index)
            for budget in budgets:
                sequence = full[:budget]
                unique = set(sequence)
                execution_cost = sum(simulated_cost(schema, rank) for rank in sequence)
                for distribution, defect_set in defect_sets.items():
                    positions = [index + 1 for index, rank in enumerate(sequence) if rank in defect_set]
                    found = len(unique & defect_set)
                    rows.append({
                        "repetition": repetition, "method": method, "budget": budget, "distribution": distribution,
                        "attempts": len(sequence), "unique_objects": len(unique), "duplicates": len(sequence) - len(unique),
                        "defects_found": found, "first_defect_attempt": positions[0] if positions else math.nan,
                        "execution_cost_units": execution_cost, "defects_per_1000_cost": 1000 * found / execution_cost,
                    })
    write_csv(RAW / "defect_distributions.csv", rows)
    return rows


def branch_tv(schema: CompiledSchema, ranks: Iterable[int]) -> float:
    sequence = list(ranks)
    intervals = branch_intervals(schema)
    target = [(stop - start) / schema.count for _, start, stop in intervals]
    observed = [sum(start <= rank < stop for rank in sequence) / len(sequence) for _, start, stop in intervals]
    return 0.5 * sum(abs(left - right) for left, right in zip(target, observed))


def distributed_experiment() -> list[dict[str, Any]]:
    schema = CompiledSchema(benchmark_schema())
    workers = 8
    rng = random.Random(SEED)
    shuffled = list(range(schema.count))
    rng.shuffle(shuffled)
    central = [shuffled[(worker * schema.count) // workers:((worker + 1) * schema.count) // workers] for worker in range(workers)]
    allocations = {
        "contiguous": schema.contiguous_partitions(workers),
        "strided": schema.strided_partitions(workers),
        "hash": schema.hash_partitions(workers, SEED),
        "permuted": schema.permuted_partitions(workers, SEED),
        "central_shuffle": central,
    }
    rows = []
    for method, parts in allocations.items():
        flat = [rank for part in parts for rank in part]
        costs = [sum(simulated_cost(schema, rank) for rank in part) for part in parts]
        counts = [len(part) for part in parts]
        rows.append({
            "method": method, "workers": workers, "assigned": len(flat), "unique": len(set(flat)),
            "overlap": len(flat) - len(set(flat)), "count_cv": statistics.pstdev(counts) / statistics.mean(counts),
            "cost_cv": statistics.pstdev(costs) / statistics.mean(costs), "max_worker_cost": max(costs),
            "mean_worker_cost": statistics.mean(costs), "mean_branch_tv": statistics.mean(branch_tv(schema, part) for part in parts),
            "coordination_units": {"contiguous": 0, "strided": 0, "hash": 0, "permuted": 1, "central_shuffle": schema.count}[method],
            "failure_recovery_ranks": len(parts[3]) - int(0.4 * len(parts[3])), "replayable_by_rank": True,
        })
    write_csv(RAW / "distributed_allocations.csv", rows)
    return rows


def statistical_analysis(defect_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    frame = pd.DataFrame(defect_rows)
    output = []
    for distribution in sorted(frame.distribution.unique()):
        for budget in sorted(frame.budget.unique()):
            subset = frame[(frame.distribution == distribution) & (frame.budget == budget)]
            focal = subset[subset.method == "pdrs_no_replacement"].sort_values("repetition").defects_found.to_numpy()
            for comparator in sorted(method for method in subset.method.unique() if method != "pdrs_no_replacement"):
                other = subset[subset.method == comparator].sort_values("repetition").defects_found.to_numpy()
                differences = focal - other
                rng = np.random.default_rng(SEED + budget + len(output))
                picks = rng.integers(0, len(differences), size=(2000, len(differences)))
                estimates = np.median(differences[picks], axis=1)
                low, high = np.quantile(estimates, [0.025, 0.975])
                output.append({
                    "distribution": distribution, "budget": int(budget), "focal": "pdrs_no_replacement", "comparator": comparator,
                    "median_paired_difference": float(np.median(differences)), "ci95_low": float(low), "ci95_high": float(high),
                    "independent_unit": "complete seeded campaign", "n_pairs": len(differences),
                    "supports_focal_advantage": bool(low > 0), "supports_comparator_advantage": bool(high < 0),
                })
    write_csv(PROCESSED / "hierarchical_bootstrap.csv", output)
    return output


def make_figures(defect_rows: list[dict[str, Any]], distributed_rows: list[dict[str, Any]], compile_rows: list[dict[str, Any]], latency_rows: list[dict[str, Any]]) -> None:
    frame = pd.DataFrame(defect_rows)
    data = frame[frame.budget == 1000].groupby(["distribution", "method"])["defects_found"].median().unstack()
    axis = data.plot(kind="bar", figsize=(13, 6))
    axis.set_ylabel("Median distinct defects found"); axis.set_xlabel(""); axis.set_title("Defect discovery depends on the defect distribution")
    axis.legend(title="Method", bbox_to_anchor=(1.02, 1), loc="upper left")
    plt.xticks(rotation=35, ha="right"); plt.tight_layout(); plt.savefig(FIGURES / "defect_distributions.pdf", bbox_inches="tight"); plt.close()

    distributed = pd.DataFrame(distributed_rows)
    figure, axis = plt.subplots(figsize=(9, 5.5)); axis.scatter(distributed.cost_cv, distributed.overlap, s=90)
    for row in distributed.itertuples():
        axis.annotate(row.method, (row.cost_cv, row.overlap), xytext=(5, 5), textcoords="offset points")
    axis.set_xlabel("Worker execution-cost coefficient of variation"); axis.set_ylabel("Duplicate rank assignments")
    axis.set_title("Disjointness does not imply balanced execution cost")
    plt.tight_layout(); plt.savefig(FIGURES / "distributed_tradeoff.pdf", bbox_inches="tight"); plt.close()

    latency = pd.DataFrame(latency_rows)
    figure, axis = plt.subplots(figsize=(9, 5.5)); axis.plot(latency.depth, latency.rank_ns_per_object, marker="o", label="rank"); axis.plot(latency.depth, latency.unrank_ns_per_object, marker="s", label="unrank")
    axis.set_xscale("log", base=2); axis.set_yscale("log"); axis.set_xlabel("Active path depth"); axis.set_ylabel("Nanoseconds per object")
    axis.set_title("Rank and unrank scale with active path depth"); axis.legend(); plt.tight_layout(); plt.savefig(FIGURES / "rank_unrank_scalability.pdf", bbox_inches="tight"); plt.close()

    compiled = pd.DataFrame(compile_rows); compiled = compiled[compiled.family.isin(["shared_dag", "expanded_tree"])]
    figure, axis = plt.subplots(figsize=(9, 5.5))
    for family, group in compiled.groupby("family"):
        axis.plot(group.branches, group.nodes, marker="o", label=f"PDRS {family}")
        axis.plot(group.branches, group.mdd_nodes, marker="x", linestyle="--", label=f"Reduced MDD {family}")
    axis.set_xlabel("Top-level branches"); axis.set_ylabel("Compiled nodes"); axis.set_title("DAG sharing and reduction control representation growth"); axis.legend()
    plt.tight_layout(); plt.savefig(FIGURES / "representation_scaling.pdf", bbox_inches="tight"); plt.close()


def checksums() -> None:
    rows = []
    for path in sorted(ROOT.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS.csv" and ".git" not in path.parts:
            rows.append({"path": path.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size})
    write_csv(ROOT / "reproducibility" / "SHA256SUMS.csv", rows)


def main() -> None:
    semantic = semantic_experiment()
    compile_rows, latency_rows = scalability_experiment()
    defect_rows = defect_experiment()
    distributed_rows = distributed_experiment()
    statistics_rows = statistical_analysis(defect_rows)
    make_figures(defect_rows, distributed_rows, compile_rows, latency_rows)
    summary = {
        "semantic": semantic,
        "defect_experiment": {"rows": len(defect_rows), "repetitions": 30, "methods": 5, "distributions": 8, "budgets": [100, 500, 1000]},
        "distributed": distributed_rows,
        "statistics": {
            "comparisons": len(statistics_rows),
            "focal_advantages": sum(row["supports_focal_advantage"] for row in statistics_rows),
            "comparator_advantages": sum(row["supports_comparator_advantage"] for row in statistics_rows),
            "uncertain": sum(not row["supports_focal_advantage"] and not row["supports_comparator_advantage"] for row in statistics_rows),
        },
        "claim_boundary": "Synthetic results concern the declared finite benchmark. Extended external-program results remain separate until their workflow completes.",
    }
    write_json(PROCESSED / "phase_1_9_summary.json", summary)
    checksums()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
