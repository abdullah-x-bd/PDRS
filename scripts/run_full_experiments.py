from __future__ import annotations

import argparse
from collections import Counter
import copy
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import statistics
import sys
import time
from typing import Any, Iterable

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import chisquare, pearsonr

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pdrs import CompiledSchema, SchemaError, SchemaLimits, load_schema
from pdrs.baselines import (
    average_metric,
    fixed_rank_bytes,
    json_bytes,
    naive_cartesian_bits,
    protobuf_wire_bytes,
    rank_varint_bytes,
    uper_subset_bits,
)
from pdrs.crypto import Ciphertext, DomainCipher
from pdrs.fuzzing import parallel_overlap, run_fuzz_methods
from pdrs.generators import (
    explicit_balanced_tree_schema,
    imbalanced_schema,
    layered_dag_schema,
    random_tree_schema,
)

SEED = 20260802
RAW = ROOT / "results" / "raw"
PROCESSED = ROOT / "results" / "processed"
FIGURES = ROOT / "results" / "figures"


def ensure_dirs() -> None:
    for path in [RAW, PROCESSED, FIGURES]:
        path.mkdir(parents=True, exist_ok=True)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"cannot write empty CSV {path}")
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def savefig(name: str) -> None:
    plt.tight_layout()
    plt.savefig(FIGURES / f"{name}.png", dpi=180, bbox_inches="tight")
    plt.savefig(FIGURES / f"{name}.svg", bbox_inches="tight")
    plt.close()


def percentile(values: list[float], p: float) -> float:
    return float(np.percentile(np.asarray(values, dtype=float), p))


def static_schemas() -> dict[str, CompiledSchema]:
    return {
        path.stem: load_schema(path)
        for path in sorted((ROOT / "schemas").glob("*.json"))
    }


def experiment_correctness(schemas: dict[str, CompiledSchema], quick: bool) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    total_objects = 0
    failures = 0
    for name, schema in schemas.items():
        if schema.count <= (20_000 if quick else 150_000):
            indices: Iterable[int] = range(schema.count)
        else:
            rng = random.Random(SEED + schema.count)
            indices = rng.sample(range(schema.count), k=min(25_000, schema.count))
        checked = 0
        local_failures = 0
        seen: set[int] = set()
        for index in indices:
            value = schema.unrank(index)
            recovered = schema.rank(value)
            checked += 1
            seen.add(recovered)
            if recovered != index:
                local_failures += 1
        failures += local_failures
        total_objects += checked
        rows.append(
            {
                "schema": name,
                "domain": schema.count,
                "objects_checked": checked,
                "unique_ranks": len(seen),
                "roundtrip_failures": local_failures,
                "mode": "exhaustive" if checked == schema.count else "sampled",
            }
        )

    generated = 150 if quick else 1000
    generated_objects = 0
    for seed in range(generated):
        schema = CompiledSchema(random_tree_schema(SEED + seed, max_depth=4))
        # These generated domains are intentionally small enough for independent exhaustive checks.
        local_seen: set[int] = set()
        for index in range(schema.count):
            value = schema.unrank(index)
            recovered = schema.rank(value)
            generated_objects += 1
            if recovered != index:
                failures += 1
            local_seen.add(recovered)
        if local_seen != set(range(schema.count)):
            failures += 1
    rows.append(
        {
            "schema": "generated_random_trees",
            "domain": "varied",
            "objects_checked": generated_objects,
            "unique_ranks": generated_objects,
            "roundtrip_failures": failures,
            "mode": f"{generated}_schemas_exhaustive",
        }
    )
    write_csv(RAW / "correctness.csv", rows)
    result = {
        "static_schemas": len(schemas),
        "generated_schemas": generated,
        "objects_checked": total_objects + generated_objects,
        "failures": failures,
    }
    (PROCESSED / "correctness_summary.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    if failures:
        raise AssertionError(f"correctness experiment found {failures} failures")
    return result


def experiment_density(schemas: dict[str, CompiledSchema]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for name, schema in schemas.items():
        pdrs_bits = schema.bit_length
        rows.append(
            {
                "schema": name,
                "domain": schema.count,
                "nodes": len(schema.nodes),
                "depth": schema.depth,
                "pdrs_fixed_bits": pdrs_bits,
                "pdrs_fixed_bytes_bits": len(schema.encode_rank(schema.unrank(0))) * 8,
                "pdrs_varint_avg_bits": average_metric(
                    schema, lambda s, value: len(rank_varint_bytes(s, value)) * 8
                ),
                "uper_subset_avg_bits": average_metric(schema, uper_subset_bits),
                "protobuf_avg_bits": average_metric(
                    schema, lambda s, value: len(protobuf_wire_bytes(s, value)) * 8
                ),
                "json_avg_bits": average_metric(
                    schema, lambda s, value: len(json_bytes(value)) * 8
                ),
                "naive_cartesian_bits": naive_cartesian_bits(schema),
            }
        )

    synthetic_rows: list[dict[str, Any]] = []
    ratios = [1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024]
    for ratio in ratios:
        schema = CompiledSchema(imbalanced_schema(f"imbalance-{ratio}", [1024, max(1, 1024 // ratio)]))
        pdrs = schema.bit_length
        local = average_metric(schema, uper_subset_bits)
        synthetic_rows.append(
            {
                "imbalance_ratio": ratio,
                "domain": schema.count,
                "pdrs_bits": pdrs,
                "uper_avg_bits": local,
                "pdrs_saving_bits": local - pdrs,
            }
        )
    write_csv(RAW / "density_static.csv", rows)
    write_csv(RAW / "density_imbalance.csv", synthetic_rows)

    methods = [
        ("PDRS fixed", "pdrs_fixed_bits"),
        ("UPER subset", "uper_subset_avg_bits"),
        ("Protobuf wire", "protobuf_avg_bits"),
        ("JSON", "json_avg_bits"),
    ]
    labels = [row["schema"] for row in rows]
    x = np.arange(len(labels))
    width = 0.19
    plt.figure(figsize=(12, 6))
    for index, (label, key) in enumerate(methods):
        plt.bar(x + (index - 1.5) * width, [row[key] for row in rows], width, label=label)
    plt.xticks(x, labels, rotation=35, ha="right")
    plt.ylabel("Average encoded bits")
    plt.title("Encoding size across structured schema corpus")
    plt.legend()
    savefig("density_comparison")

    plt.figure(figsize=(8, 5))
    plt.plot(
        [row["imbalance_ratio"] for row in synthetic_rows],
        [row["pdrs_saving_bits"] for row in synthetic_rows],
        marker="o",
    )
    plt.xscale("log", base=2)
    plt.xlabel("Large-to-small branch size ratio")
    plt.ylabel("Average bits saved versus local field packing")
    plt.title("Whole-domain ranking benefit under branch imbalance")
    savefig("density_imbalance")

    return {
        "schemas": len(rows),
        "median_pdrs_vs_protobuf_saving_bits": statistics.median(
            row["protobuf_avg_bits"] - row["pdrs_fixed_bits"] for row in rows
        ),
        "median_pdrs_vs_uper_saving_bits": statistics.median(
            row["uper_subset_avg_bits"] - row["pdrs_fixed_bits"] for row in rows
        ),
    }


def _time_call(callable_, repetitions: int) -> list[float]:
    times: list[float] = []
    for _ in range(repetitions):
        start = time.perf_counter_ns()
        callable_()
        times.append((time.perf_counter_ns() - start) / 1_000_000)
    return times


def experiment_runtime(schemas: dict[str, CompiledSchema], quick: bool) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    operation_count = 1500 if quick else 6000
    rounds = 3 if quick else 7
    for name, schema in schemas.items():
        rng = random.Random(SEED + schema.count)
        indices = [rng.randrange(schema.count) for _ in range(operation_count)]
        values = [schema.unrank(index) for index in indices]
        rank_times = _time_call(lambda: [schema.rank(value) for value in values], rounds)
        unrank_times = _time_call(lambda: [schema.unrank(index) for index in indices], rounds)
        sample_rng = random.Random(SEED)
        sample_times = _time_call(lambda: [schema.sample(sample_rng) for _ in indices], rounds)
        rows.append(
            {
                "family": "static",
                "schema": name,
                "nodes": len(schema.nodes),
                "edges": schema.edge_count,
                "depth": schema.depth,
                "domain_bits": schema.bit_length,
                "rank_us_per_op": statistics.median(rank_times) * 1000 / operation_count,
                "unrank_us_per_op": statistics.median(unrank_times) * 1000 / operation_count,
                "sample_us_per_op": statistics.median(sample_times) * 1000 / operation_count,
                "rank_p95_us_per_op": percentile(rank_times, 95) * 1000 / operation_count,
                "unrank_p95_us_per_op": percentile(unrank_times, 95) * 1000 / operation_count,
            }
        )

    scaling_rows: list[dict[str, Any]] = []
    depths = [2, 4, 8, 16, 32, 64, 128, 256] if quick else [2, 4, 8, 16, 32, 64, 128, 256, 512, 1024]
    for depth in depths:
        document = layered_dag_schema(
            f"dag-d{depth}", depth=depth, branch_factor=4, range_width=2
        )
        compile_times = _time_call(lambda: CompiledSchema(document), rounds)
        schema = CompiledSchema(document)
        index = schema.count // 2
        value = schema.unrank(index)
        rank_times = _time_call(lambda: [schema.rank(value) for _ in range(500)], rounds)
        unrank_times = _time_call(lambda: [schema.unrank(index) for _ in range(500)], rounds)
        scaling_rows.append(
            {
                "family": "layered_dag",
                "depth": depth,
                "nodes": len(schema.nodes),
                "edges": schema.edge_count,
                "domain_bits": schema.bit_length,
                "compile_ms": statistics.median(compile_times),
                "rank_us_per_op": statistics.median(rank_times) * 2,
                "unrank_us_per_op": statistics.median(unrank_times) * 2,
            }
        )

    explicit_depths = [3, 4, 5, 6, 7] if quick else [3, 4, 5, 6, 7, 8, 9]
    for depth in explicit_depths:
        document = explicit_balanced_tree_schema(f"tree-d{depth}", depth, 3)
        compile_times = _time_call(lambda: CompiledSchema(document), rounds)
        schema = CompiledSchema(document)
        scaling_rows.append(
            {
                "family": "explicit_tree",
                "depth": depth,
                "nodes": len(schema.nodes),
                "edges": schema.edge_count,
                "domain_bits": schema.bit_length,
                "compile_ms": statistics.median(compile_times),
                "rank_us_per_op": "",
                "unrank_us_per_op": "",
            }
        )

    write_csv(RAW / "runtime_static.csv", rows)
    write_csv(RAW / "runtime_scaling.csv", scaling_rows)

    dag = [row for row in scaling_rows if row["family"] == "layered_dag"]
    plt.figure(figsize=(8, 5))
    plt.plot([row["depth"] for row in dag], [row["rank_us_per_op"] for row in dag], marker="o", label="Rank")
    plt.plot([row["depth"] for row in dag], [row["unrank_us_per_op"] for row in dag], marker="o", label="Unrank")
    plt.xlabel("Path depth")
    plt.ylabel("Median microseconds per operation")
    plt.title("Rank and unrank scaling with path depth")
    plt.legend()
    savefig("runtime_depth_scaling")

    plt.figure(figsize=(8, 5))
    for family in ["layered_dag", "explicit_tree"]:
        subset = [row for row in scaling_rows if row["family"] == family]
        plt.plot([row["nodes"] for row in subset], [row["compile_ms"] for row in subset], marker="o", label=family)
    plt.xscale("log")
    plt.yscale("log")
    plt.xlabel("Schema nodes")
    plt.ylabel("Median compile time, ms")
    plt.title("Compilation scaling")
    plt.legend()
    savefig("compile_scaling")

    environment = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (RAW / "runtime_environment.json").write_text(json.dumps(environment, indent=2) + "\n", encoding="utf-8")
    return {
        "operation_count_per_schema": operation_count,
        "static_schemas": len(rows),
        "scaling_points": len(scaling_rows),
        "median_rank_us": statistics.median(row["rank_us_per_op"] for row in rows),
        "median_unrank_us": statistics.median(row["unrank_us_per_op"] for row in rows),
    }


def _root_expectations(schema: CompiledSchema) -> tuple[list[str], list[float]]:
    root = schema.nodes[schema.root]
    from pdrs.core import ChoiceNode
    if not isinstance(root, ChoiceNode):
        return ["root"], [1.0]
    labels = [branch.value for branch in root.branches]
    probs = [schema._count(branch.target) / schema.count for branch in root.branches]
    return labels, probs


def experiment_uniformity(schemas: dict[str, CompiledSchema], quick: bool) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    branch_rows: list[dict[str, Any]] = []
    sample_count = 30_000 if quick else 150_000
    selected = ["permit", "calendar", "telecom", "fuzz_target", "compiler_ast"]
    for name in selected:
        schema = schemas[name]
        rng = random.Random(SEED + schema.count)
        buckets = 100
        observed = [0] * buckets
        root_counts: Counter[Any] = Counter()
        for _ in range(sample_count):
            value = schema.sample(rng)
            rank = schema.rank(value)
            bucket = min(buckets - 1, (rank * buckets) // schema.count)
            observed[bucket] += 1
            root_counts[value[0] if value else "root"] += 1
        bucket_sizes = [0] * buckets
        for rank in range(schema.count):
            bucket_sizes[min(buckets - 1, (rank * buckets) // schema.count)] += 1
        expected = [sample_count * size / schema.count for size in bucket_sizes]
        statistic, p_value = chisquare(observed, expected)
        expected_probabilities = [size / schema.count for size in bucket_sizes]
        tv = 0.5 * sum(abs(o / sample_count - probability) for o, probability in zip(observed, expected_probabilities))
        rows.append(
            {
                "schema": name,
                "samples": sample_count,
                "rank_buckets": buckets,
                "chi_square": statistic,
                "p_value": p_value,
                "total_variation": tv,
                "max_relative_bucket_deviation": max(abs(o - expected[0]) / expected[0] for o in observed),
            }
        )
        labels, probabilities = _root_expectations(schema)
        for label, probability in zip(labels, probabilities):
            observed_probability = root_counts[label] / sample_count
            branch_rows.append(
                {
                    "schema": name,
                    "branch": label,
                    "expected_probability": probability,
                    "observed_probability": observed_probability,
                    "ratio": observed_probability / probability if probability else math.nan,
                }
            )

    # Compare object-uniform PDRS sampling against locally uniform grammar sampling.
    schema = schemas["fuzz_target"]
    from pdrs.fuzzing import direct_grammar_value
    grammar_rng = random.Random(SEED)
    grammar_counts: Counter[Any] = Counter()
    for _ in range(sample_count):
        grammar_counts[direct_grammar_value(schema, grammar_rng)[0]] += 1
    labels, probabilities = _root_expectations(schema)
    comparison: list[dict[str, Any]] = []
    pdrs_lookup = {
        row["branch"]: row["observed_probability"]
        for row in branch_rows
        if row["schema"] == "fuzz_target"
    }
    for label, probability in zip(labels, probabilities):
        comparison.append(
            {
                "branch": label,
                "object_share": probability,
                "pdrs_share": pdrs_lookup[label],
                "direct_grammar_share": grammar_counts[label] / sample_count,
            }
        )

    write_csv(RAW / "uniformity.csv", rows)
    write_csv(RAW / "uniformity_branches.csv", branch_rows)
    write_csv(RAW / "uniformity_fuzz_branch_comparison.csv", comparison)

    x = np.arange(len(comparison))
    width = 0.26
    plt.figure(figsize=(8, 5))
    plt.bar(x - width, [row["object_share"] for row in comparison], width, label="True object share")
    plt.bar(x, [row["pdrs_share"] for row in comparison], width, label="PDRS sampled")
    plt.bar(x + width, [row["direct_grammar_share"] for row in comparison], width, label="Direct grammar")
    plt.xticks(x, [row["branch"] for row in comparison])
    plt.ylabel("Probability")
    plt.title("Object-uniform versus branch-uniform generation")
    plt.legend()
    savefig("uniformity_branch_bias")

    return {
        "schemas": len(rows),
        "samples_per_schema": sample_count,
        "max_total_variation": max(row["total_variation"] for row in rows),
        "minimum_p_value": min(row["p_value"] for row in rows),
    }


def experiment_fuzzing(schemas: dict[str, CompiledSchema], quick: bool) -> dict[str, Any]:
    schema = schemas["fuzz_target"]
    bug_rng = random.Random(SEED)
    bug_ranks = set(bug_rng.sample(range(schema.count), k=64))
    budget = 1500 if quick else 3500
    repetitions = 10 if quick else 40
    rows: list[dict[str, Any]] = []
    for repetition in range(repetitions):
        for run in run_fuzz_methods(
            schema,
            budget=budget,
            seed=SEED + repetition * 97,
            bug_ranks=bug_ranks,
        ):
            rows.append(
                {
                    "repetition": repetition,
                    "method": run.method,
                    "attempts": run.attempts,
                    "valid": run.valid,
                    "validity_rate": run.validity_rate,
                    "unique": run.unique,
                    "unique_rate": run.unique_rate,
                    "duplicates": run.duplicate,
                    "root_branches": run.root_branches,
                    "nodes_covered": run.nodes_covered,
                    "bugs_found": run.bugs_found,
                    "first_bug_attempt": run.first_bug_attempt if run.first_bug_attempt is not None else budget + 1,
                }
            )
    overlap_rows = []
    for repetition in range(repetitions):
        overlap = parallel_overlap(
            schema,
            workers=4,
            budget_per_worker=min(500, schema.count // 4),
            seed=SEED + repetition,
        )
        overlap_rows.append({"repetition": repetition, **overlap})
    write_csv(RAW / "fuzzing_runs.csv", rows)
    write_csv(RAW / "fuzzing_parallel_overlap.csv", overlap_rows)

    methods = sorted(set(row["method"] for row in rows))
    summary_rows: list[dict[str, Any]] = []
    for method in methods:
        subset = [row for row in rows if row["method"] == method]
        unique_values = [row["unique"] for row in subset]
        bug_values = [row["bugs_found"] for row in subset]
        first_values = [row["first_bug_attempt"] for row in subset]
        summary_rows.append(
            {
                "method": method,
                "median_validity_rate": statistics.median(row["validity_rate"] for row in subset),
                "median_unique": statistics.median(unique_values),
                "unique_q025": percentile(unique_values, 2.5),
                "unique_q975": percentile(unique_values, 97.5),
                "median_duplicate": statistics.median(row["duplicates"] for row in subset),
                "median_bugs_found": statistics.median(bug_values),
                "bugs_q025": percentile(bug_values, 2.5),
                "bugs_q975": percentile(bug_values, 97.5),
                "median_first_bug_attempt": statistics.median(first_values),
                "first_bug_q025": percentile(first_values, 2.5),
                "first_bug_q975": percentile(first_values, 97.5),
            }
        )
    pdrs_row = next(row for row in summary_rows if row["method"] == "pdrs_without_replacement")
    for row in summary_rows:
        row["unique_relative_to_pdrs"] = row["median_unique"] / pdrs_row["median_unique"]
        row["bugs_relative_to_pdrs"] = row["median_bugs_found"] / pdrs_row["median_bugs_found"]
    write_csv(PROCESSED / "fuzzing_summary.csv", summary_rows)

    display_names = {
        "direct_grammar": "Direct grammar",
        "mutation": "Mutation",
        "naive_rejection": "Naive rejection",
        "pdrs_without_replacement": "PDRS without replacement",
    }
    x = np.arange(len(summary_rows))
    unique_medians = [row["median_unique"] for row in summary_rows]
    unique_errors = [
        [median - row["unique_q025"] for median, row in zip(unique_medians, summary_rows)],
        [row["unique_q975"] - median for median, row in zip(unique_medians, summary_rows)],
    ]
    plt.figure(figsize=(9, 5))
    plt.bar(x, unique_medians, yerr=unique_errors, capsize=4)
    plt.xticks(x, [display_names[row["method"]] for row in summary_rows], rotation=20, ha="right")
    plt.ylabel("Unique valid objects")
    plt.title(f"Structured fuzzing coverage at {budget} attempts, median and 95% interval")
    savefig("fuzzing_unique_coverage")

    bug_medians = [row["median_bugs_found"] for row in summary_rows]
    bug_errors = [
        [median - row["bugs_q025"] for median, row in zip(bug_medians, summary_rows)],
        [row["bugs_q975"] - median for median, row in zip(bug_medians, summary_rows)],
    ]
    plt.figure(figsize=(9, 5))
    plt.bar(x, bug_medians, yerr=bug_errors, capsize=4)
    plt.xticks(x, [display_names[row["method"]] for row in summary_rows], rotation=20, ha="right")
    plt.ylabel("Distinct seeded bugs reached")
    plt.title("Bug discovery, median and 95% interval")
    savefig("fuzzing_bug_discovery")

    return {
        "budget": budget,
        "repetitions": repetitions,
        "seeded_bugs": len(bug_ranks),
        "pdrs_parallel_overlap": statistics.median(row["pdrs_overlap_fraction"] for row in overlap_rows),
        "grammar_parallel_overlap": statistics.median(row["grammar_overlap_fraction"] for row in overlap_rows),
        "summary": summary_rows,
    }


def _evolution_variants(base: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    variants: list[tuple[str, dict[str, Any]]] = []

    append = copy.deepcopy(base)
    append["version"] = "append"
    append["nodes"]["new_serial"] = {"type": "range", "field": "serial", "start": 0, "stop": 49, "target": "end"}
    append["nodes"]["permit_type"]["branches"].append({"value": "new", "target": "new_serial"})
    variants.append(("append_root_branch", append))

    insert = copy.deepcopy(append)
    insert["version"] = "insert"
    branch = insert["nodes"]["permit_type"]["branches"].pop()
    insert["nodes"]["permit_type"]["branches"].insert(0, branch)
    variants.append(("insert_root_branch_first", insert))

    reorder = copy.deepcopy(base)
    reorder["version"] = "reorder"
    reorder["nodes"]["permit_type"]["branches"].reverse()
    variants.append(("reverse_root_order", reorder))

    expand_first = copy.deepcopy(base)
    expand_first["version"] = "expand-first"
    expand_first["nodes"]["research_serial"]["stop"] = 149
    variants.append(("expand_first_branch_range", expand_first))

    expand_last = copy.deepcopy(base)
    expand_last["version"] = "expand-last"
    expand_last["nodes"]["experimental_serial"]["stop"] = 79
    variants.append(("expand_last_branch_range", expand_last))

    remove = copy.deepcopy(base)
    remove["version"] = "remove"
    remove["nodes"]["permit_type"]["branches"] = [
        branch for branch in remove["nodes"]["permit_type"]["branches"]
        if branch["value"] != "experimental"
    ]
    del remove["nodes"]["experimental_lab"]
    del remove["nodes"]["experimental_serial"]
    variants.append(("remove_last_branch", remove))
    return variants


def experiment_evolution(schemas: dict[str, CompiledSchema]) -> dict[str, Any]:
    base_path = ROOT / "schemas" / "permit.json"
    base_doc = json.loads(base_path.read_text(encoding="utf-8"))
    base = schemas["permit"]
    values = [base.unrank(index) for index in range(base.count)]
    rows: list[dict[str, Any]] = []
    for mutation, document in _evolution_variants(base_doc):
        changed = CompiledSchema(document)
        common = 0
        moved = 0
        displacements: list[int] = []
        for value in values:
            try:
                new_rank = changed.rank(value)
            except SchemaError:
                continue
            old_rank = base.rank(value)
            common += 1
            displacement = new_rank - old_rank
            displacements.append(displacement)
            if displacement:
                moved += 1
        rows.append(
            {
                "mutation": mutation,
                "base_domain": base.count,
                "new_domain": changed.count,
                "common_objects": common,
                "moved_objects": moved,
                "churn_fraction": moved / common if common else math.nan,
                "mean_absolute_displacement": statistics.mean(abs(value) for value in displacements) if displacements else math.nan,
                "max_absolute_displacement": max((abs(value) for value in displacements), default=0),
                "median_displacement": statistics.median(displacements) if displacements else math.nan,
            }
        )
    write_csv(RAW / "schema_evolution.csv", rows)

    plt.figure(figsize=(9, 5))
    plt.barh([row["mutation"] for row in rows], [100 * row["churn_fraction"] for row in rows])
    plt.xlabel("Unchanged objects with changed rank, percent")
    plt.title("Rank churn under schema evolution")
    savefig("schema_evolution_churn")
    return {
        "mutations": len(rows),
        "minimum_churn": min(row["churn_fraction"] for row in rows),
        "maximum_churn": max(row["churn_fraction"] for row in rows),
        "rows": rows,
    }


def token_distance(left: list[Any], right: list[Any]) -> int:
    overlap = min(len(left), len(right))
    return sum(left[i] != right[i] for i in range(overlap)) + abs(len(left) - len(right))


def experiment_faults(schemas: dict[str, CompiledSchema], quick: bool) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    sample_size = 300 if quick else 1500
    for name, schema in schemas.items():
        rng = random.Random(SEED + schema.count)
        ranks = rng.sample(range(schema.count), k=min(sample_size, schema.count))
        flips = 0
        valid_corruptions = 0
        semantic_distances: list[int] = []
        detected_crc = 0
        for rank in ranks:
            original = schema.unrank(rank)
            for bit in range(schema.bit_length):
                flips += 1
                altered = rank ^ (1 << bit)
                # A CRC or MAC over the rank detects every single-bit alteration.
                detected_crc += 1
                if altered < schema.count:
                    valid_corruptions += 1
                    semantic_distances.append(token_distance(original, schema.unrank(altered)))
        rows.append(
            {
                "schema": name,
                "domain": schema.count,
                "bit_width": schema.bit_length,
                "single_bit_flips": flips,
                "valid_corruptions": valid_corruptions,
                "valid_corruption_fraction": valid_corruptions / flips if flips else 0,
                "mean_token_distance": statistics.mean(semantic_distances) if semantic_distances else 0,
                "crc_detection_fraction": detected_crc / flips if flips else 0,
            }
        )
    write_csv(RAW / "fault_propagation.csv", rows)
    plt.figure(figsize=(9, 5))
    plt.bar([row["schema"] for row in rows], [100 * row["valid_corruption_fraction"] for row in rows])
    plt.xticks(rotation=35, ha="right")
    plt.ylabel("Single-bit flips decoding to another valid object, percent")
    plt.title("Raw dense ranks have weak intrinsic error detection")
    savefig("fault_valid_corruption")
    return {
        "schemas": len(rows),
        "median_valid_corruption_fraction": statistics.median(row["valid_corruption_fraction"] for row in rows),
        "crc_single_bit_detection": min(row["crc_detection_fraction"] for row in rows),
    }


def experiment_scalability_and_timing(quick: bool) -> dict[str, Any]:
    limit_rows: list[dict[str, Any]] = []
    cases = [
        (
            "node_limit",
            explicit_balanced_tree_schema("node-limit", 6, 3),
            SchemaLimits(max_nodes=100),
        ),
        (
            "depth_limit",
            layered_dag_schema("depth-limit", depth=100, branch_factor=2),
            SchemaLimits(max_depth=50),
        ),
        (
            "domain_bit_limit",
            layered_dag_schema("domain-limit", depth=100, branch_factor=4),
            SchemaLimits(max_domain_bits=100),
        ),
        (
            "range_limit",
            {
                "root": "r",
                "nodes": {
                    "r": {"type": "range", "start": 0, "stop": 1_000_000, "target": "end"},
                    "end": {"type": "terminal"},
                },
            },
            SchemaLimits(max_range_width=1000),
        ),
    ]
    for name, document, limits in cases:
        start = time.perf_counter_ns()
        rejected = False
        message = ""
        try:
            CompiledSchema(document, limits=limits)
        except SchemaError as error:
            rejected = True
            message = str(error)
        elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
        limit_rows.append(
            {"case": name, "rejected": rejected, "elapsed_ms": elapsed_ms, "message": message}
        )
        if not rejected:
            raise AssertionError(f"resource attack {name} was not rejected")
    write_csv(RAW / "resource_limits.csv", limit_rows)

    # Timing variation across a 256-way root choice.
    document = imbalanced_schema("timing-choice", [1] * 256)
    schema = CompiledSchema(document)
    repetitions = 1000 if quick else 5000
    rows: list[dict[str, Any]] = []
    for branch_index in range(256):
        value = [f"branch_{branch_index}", 0]
        rank_samples: list[float] = []
        unrank_samples: list[float] = []
        rank_value = schema.rank(value)
        for _ in range(5):
            start = time.perf_counter_ns()
            for _ in range(repetitions):
                schema.rank(value)
            rank_samples.append((time.perf_counter_ns() - start) / repetitions)
            start = time.perf_counter_ns()
            for _ in range(repetitions):
                schema.unrank(rank_value)
            unrank_samples.append((time.perf_counter_ns() - start) / repetitions)
        rows.append(
            {
                "branch_index": branch_index,
                "rank_ns": statistics.median(rank_samples),
                "unrank_ns": statistics.median(unrank_samples),
            }
        )
    write_csv(RAW / "timing_branch_index.csv", rows)
    rank_corr = pearsonr([row["branch_index"] for row in rows], [row["rank_ns"] for row in rows])
    unrank_corr = pearsonr([row["branch_index"] for row in rows], [row["unrank_ns"] for row in rows])

    plt.figure(figsize=(9, 5))
    plt.plot([row["branch_index"] for row in rows], [row["rank_ns"] for row in rows], label="Rank")
    plt.plot([row["branch_index"] for row in rows], [row["unrank_ns"] for row in rows], label="Unrank")
    plt.xlabel("Choice branch index")
    plt.ylabel("Median nanoseconds per operation")
    plt.title("Branch-index timing variation in Python reference implementation")
    plt.legend()
    savefig("timing_branch_variation")
    return {
        "resource_attacks_rejected": sum(row["rejected"] for row in limit_rows),
        "resource_attacks": len(limit_rows),
        "rank_branch_index_correlation": rank_corr.statistic,
        "rank_branch_index_p": rank_corr.pvalue,
        "unrank_branch_index_correlation": unrank_corr.statistic,
        "unrank_branch_index_p": unrank_corr.pvalue,
        "constant_time_claim": False,
    }


def hamming_distance(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def experiment_crypto(schemas: dict[str, CompiledSchema], quick: bool) -> dict[str, Any]:
    key = hashlib.sha256(b"PDRS experiment key 2026-08-02").digest()
    rows: list[dict[str, Any]] = []
    avalanche_rows: list[dict[str, Any]] = []
    selected = ["permit", "telecom", "fuzz_target", "administrative"]
    for name in selected:
        schema = schemas[name]
        cipher = DomainCipher(schema, key)
        exhaustive = schema.count <= (6000 if quick else 12_000)
        if exhaustive:
            ranks = range(schema.count)
        else:
            rng = random.Random(SEED + schema.count)
            ranks = rng.sample(range(schema.count), k=min(10_000, schema.count))
        encrypted: set[int] = set()
        cycle_counts: list[int] = []
        failures = 0
        for rank in ranks:
            encrypted_rank, cycles = cipher.encrypt_rank(rank, b"context-A")
            recovered, inverse_cycles = cipher.decrypt_rank(encrypted_rank, b"context-A")
            encrypted.add(encrypted_rank)
            cycle_counts.append(cycles)
            if recovered != rank or inverse_cycles <= 0:
                failures += 1
        checked = schema.count if exhaustive else len(encrypted)
        if exhaustive and len(encrypted) != schema.count:
            failures += 1

        rng = random.Random(SEED + schema.count)
        tamper_detected = 0
        tamper_trials = 200
        for _ in range(tamper_trials):
            value = schema.unrank(rng.randrange(schema.count))
            ciphertext = cipher.encrypt(value, b"context-A")
            bad = Ciphertext(
                value=ciphertext.value,
                tag_hex=("00" if not ciphertext.tag_hex.startswith("00") else "ff") + ciphertext.tag_hex[2:],
                tweak_hex=ciphertext.tweak_hex,
            )
            try:
                cipher.decrypt(bad)
            except SchemaError:
                tamper_detected += 1

        avalanche_samples = 300 if quick else 1500
        for _ in range(avalanche_samples):
            rank = rng.randrange(schema.count)
            bit = rng.randrange(schema.bit_length)
            neighbor = rank ^ (1 << bit)
            if neighbor >= schema.count:
                continue
            left, _ = cipher.encrypt_rank(rank, b"context-A")
            right, _ = cipher.encrypt_rank(neighbor, b"context-A")
            tweak_other, _ = cipher.encrypt_rank(rank, b"context-B")
            avalanche_rows.append(
                {
                    "schema": name,
                    "input_bit": bit,
                    "plaintext_rank": rank,
                    "cipher_hamming_fraction": hamming_distance(left, right) / cipher.width,
                    "tweak_hamming_fraction": hamming_distance(left, tweak_other) / cipher.width,
                }
            )

        rows.append(
            {
                "schema": name,
                "domain": schema.count,
                "checked": checked,
                "exhaustive": exhaustive,
                "permutation_failures": failures,
                "unique_cipher_ranks": len(encrypted),
                "mean_cycle_walk_iterations": statistics.mean(cycle_counts),
                "max_cycle_walk_iterations": max(cycle_counts),
                "tamper_detection_fraction": tamper_detected / tamper_trials,
            }
        )
    write_csv(RAW / "crypto_permutation.csv", rows)
    write_csv(RAW / "crypto_avalanche.csv", avalanche_rows)

    schemas_order = selected
    means = [
        statistics.mean(row["cipher_hamming_fraction"] for row in avalanche_rows if row["schema"] == name)
        for name in schemas_order
    ]
    tweak_means = [
        statistics.mean(row["tweak_hamming_fraction"] for row in avalanche_rows if row["schema"] == name)
        for name in schemas_order
    ]
    x = np.arange(len(schemas_order))
    width = 0.35
    plt.figure(figsize=(9, 5))
    plt.bar(x - width / 2, means, width, label="One plaintext bit changed")
    plt.bar(x + width / 2, tweak_means, width, label="Tweak changed")
    plt.axhline(0.5, linestyle="--", label="Idealized 0.5 reference")
    plt.xticks(x, schemas_order, rotation=25, ha="right")
    plt.ylabel("Cipher-rank bit difference fraction")
    plt.title("Research domain-permutation diffusion")
    plt.legend()
    savefig("crypto_avalanche")
    if any(row["permutation_failures"] for row in rows):
        raise AssertionError("crypto permutation experiment found failures")
    return {
        "schemas": len(rows),
        "permutation_failures": sum(row["permutation_failures"] for row in rows),
        "minimum_tamper_detection": min(row["tamper_detection_fraction"] for row in rows),
        "mean_avalanche_fraction": statistics.mean(row["cipher_hamming_fraction"] for row in avalanche_rows),
        "mean_tweak_fraction": statistics.mean(row["tweak_hamming_fraction"] for row in avalanche_rows),
        "deployment_ready": False,
    }


def write_summary(summary: dict[str, Any]) -> None:
    (PROCESSED / "experiment_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# Generated experimental evidence summary",
        "",
        "This file is generated by `scripts/run_full_experiments.py`.",
        "",
    ]
    for section, result in summary.items():
        lines.append(f"## {section.replace('_', ' ').title()}")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(result, indent=2))
        lines.append("```")
        lines.append("")
    (PROCESSED / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def checksums() -> None:
    rows: list[dict[str, str]] = []
    for directory in [RAW, PROCESSED, FIGURES]:
        for path in sorted(directory.glob("*")):
            if path.is_file() and path.name != "SHA256SUMS.csv":
                rows.append(
                    {
                        "path": str(path.relative_to(ROOT)),
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    }
                )
    write_csv(PROCESSED / "SHA256SUMS.csv", rows)


def main() -> None:
    import subprocess

    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="run reduced CI-sized evidence suite")
    parser.add_argument(
        "--stage",
        choices=[
            "correctness",
            "density",
            "runtime",
            "uniformity",
            "fuzzing",
            "schema_evolution",
            "fault_propagation",
            "scalability_and_timing",
            "crypto_adapter",
        ],
    )
    args = parser.parse_args()
    ensure_dirs()
    schemas = static_schemas()
    stage_functions = {
        "correctness": lambda: experiment_correctness(schemas, args.quick),
        "density": lambda: experiment_density(schemas),
        "runtime": lambda: experiment_runtime(schemas, args.quick),
        "uniformity": lambda: experiment_uniformity(schemas, args.quick),
        "fuzzing": lambda: experiment_fuzzing(schemas, args.quick),
        "schema_evolution": lambda: experiment_evolution(schemas),
        "fault_propagation": lambda: experiment_faults(schemas, args.quick),
        "scalability_and_timing": lambda: experiment_scalability_and_timing(args.quick),
        "crypto_adapter": lambda: experiment_crypto(schemas, args.quick),
    }
    if args.stage:
        print(f"START {args.stage}", flush=True)
        started = time.perf_counter()
        result = stage_functions[args.stage]()
        stage_path = PROCESSED / f"stage_{args.stage}.json"
        stage_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(f"DONE {args.stage} {time.perf_counter() - started:.3f}s", flush=True)
        print(json.dumps(result, indent=2))
        return

    summary: dict[str, Any] = {}
    for stage in stage_functions:
        command = [sys.executable, str(Path(__file__).resolve()), "--stage", stage]
        if args.quick:
            command.append("--quick")
        subprocess.run(command, check=True, env=os.environ.copy())
        summary[stage] = json.loads(
            (PROCESSED / f"stage_{stage}.json").read_text(encoding="utf-8")
        )
    write_summary(summary)
    checksums()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
