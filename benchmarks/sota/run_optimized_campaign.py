from __future__ import annotations

"""Optimized execution of the matched six-system comparison.

Each method produces one maximum-budget sequence for every domain and
repetition. Smaller-budget measurements are exact prefixes of that sequence.
This preserves matched campaign semantics while avoiding three separate
external tool launches for the three reported budget levels.
"""

import argparse
import csv
import json
import math
from pathlib import Path
import random
import statistics
import time

import numpy as np
from scipy.stats import chisquare

import run_comparison as rc


# CombOL treats `dummy` as an implicit neutral symbol and omits it from its
# explicit parameter map. Filter reserved symbols and use unit weight for all
# real atoms, so every complete padded object has equal product weight.
from combol.context import Context

_original_translate = Context._translate_str_params


def _translate_unit_weights(self: Context, params: dict[str, float]):
    normalized = {key: 1.0 for key in params if key in self.variable_key_map}
    return _original_translate(self, normalized)


Context._translate_str_params = _translate_unit_weights

_COMBOL_SAMPLERS: dict[str, object] = {}


def combol_cached(domain: rc.Domain, budget: int, seed_value: int) -> tuple[list[int], float]:
    import combol

    sampler = _COMBOL_SAMPLERS.get(domain.name)
    if sampler is None:
        specification, parameters = rc.combol_spec(domain)
        cls = combol.parse(specification)
        sampler = cls.sampler(parameters)
        _COMBOL_SAMPLERS[domain.name] = sampler

    random.seed(seed_value)
    np.random.seed(seed_value % (2**32))
    start = time.perf_counter()
    ranks = [rc.parse_combol(domain, sampler.sample()) for _ in range(budget)]
    return ranks, time.perf_counter() - start


rc.combol_sequence = combol_cached


def budgets(domain: rc.Domain) -> tuple[int, ...]:
    return tuple(sorted({min(requested, domain.count) for requested in rc.BUDGETS}))


def aggregate_uniformity(
    run_sequences: dict[tuple[str, str, int, int], list[int]],
) -> list[dict]:
    rows: list[dict] = []
    for domain in rc.DOMAINS:
        for budget in budgets(domain):
            for method in rc.METHODS:
                combined: list[int] = []
                for repetition in range(rc.REPETITIONS):
                    combined.extend(run_sequences[(method, domain.name, budget, repetition)])
                observed = np.bincount(combined, minlength=domain.count).astype(float)
                expected = np.full(domain.count, len(combined) / domain.count)
                tv = 0.5 * float(
                    np.abs(observed / len(combined) - 1 / domain.count).sum()
                )
                branch_observed = np.zeros(len(domain.branches))
                for rank, count in enumerate(observed):
                    branch_observed[domain.branch_of_rank(rank)] += count
                branch_expected = np.asarray(domain.branch_sizes, dtype=float) / domain.count
                branch_tv = 0.5 * float(
                    np.abs(branch_observed / len(combined) - branch_expected).sum()
                )
                p_value = math.nan
                if expected.min() >= 5:
                    _, p_value = chisquare(observed, expected)
                rows.append(
                    {
                        "method": method,
                        "domain": domain.name,
                        "budget": budget,
                        "samples": len(combined),
                        "object_total_variation": tv,
                        "branch_total_variation": branch_tv,
                        "chi_square_p": p_value,
                    }
                )
    return rows


def worker_overlap(
    run_sequences: dict[tuple[str, str, int, int], list[int]],
) -> list[dict]:
    rows: list[dict] = []
    for domain in rc.DOMAINS:
        sequence_budget = max(budget for budget in budgets(domain) if budget <= min(500, domain.count))
        worker_budget = min(500, max(1, domain.count // 4))
        feat, _ = rc.load_haskell("feat", domain)
        small, _ = rc.load_haskell("smallcheck", domain)
        coordinated = {
            "pdrs": [
                set(range((worker * domain.count) // 4, ((worker + 1) * domain.count) // 4))
                for worker in range(4)
            ],
            "feat": [set(feat[worker::4]) for worker in range(4)],
            "smallcheck": [set(small[worker::4]) for worker in range(4)],
        }
        for method in rc.METHODS:
            if method in coordinated:
                groups = [set(list(group)[:worker_budget]) for group in coordinated[method]]
            else:
                groups = [
                    set(run_sequences[(method, domain.name, sequence_budget, worker)])
                    for worker in range(4)
                ]
            total = sum(len(group) for group in groups)
            union = len(set().union(*groups))
            rows.append(
                {
                    "method": method,
                    "domain": domain.name,
                    "workers": 4,
                    "budget_per_worker": worker_budget,
                    "sequence_budget": sequence_budget,
                    "total_unique_worker_outputs": total,
                    "union": union,
                    "overlap_fraction": (total - union) / total if total else 0.0,
                }
            )
    return rows


def run() -> None:
    rc.ensure_dirs()
    exact = rc.exact_evidence()
    rc.write_csv(rc.RAW / "exact_enumeration.csv", exact)

    rows: list[dict] = []
    sequences: dict[tuple[str, str, int, int], list[int]] = {}
    source_runs: list[dict] = []

    for domain in rc.DOMAINS:
        feat_all, _ = rc.load_haskell("feat", domain)
        small_all, _ = rc.load_haskell("smallcheck", domain)
        domain_budgets = budgets(domain)
        maximum = max(domain_budgets)
        for repetition in range(rc.REPETITIONS):
            for method in rc.METHODS:
                full_sequence, elapsed = rc.method_sequence(
                    method,
                    domain,
                    maximum,
                    repetition,
                    feat_all,
                    small_all,
                )
                if len(full_sequence) != maximum:
                    raise AssertionError(
                        f"{method} produced {len(full_sequence)} values for "
                        f"{domain.name}, expected {maximum}"
                    )
                source_runs.append(
                    {
                        "method": method,
                        "domain": domain.name,
                        "repetition": repetition,
                        "source_budget": maximum,
                        "elapsed_s": elapsed,
                        "objects_per_s": maximum / elapsed if elapsed > 0 else math.inf,
                    }
                )
                for budget in domain_budgets:
                    prefix = full_sequence[:budget]
                    sequences[(method, domain.name, budget, repetition)] = prefix
                    row = rc.assess(
                        method,
                        domain,
                        prefix,
                        elapsed,
                        repetition,
                        budget,
                    )
                    row["source_budget"] = maximum
                    row["source_elapsed_s"] = elapsed
                    row["source_objects_per_s"] = maximum / elapsed if elapsed > 0 else math.inf
                    rows.append(row)

    rc.write_csv(rc.RAW / "generation_runs.csv", rows)
    rc.write_csv(rc.RAW / "source_campaigns.csv", source_runs)

    uniformity = aggregate_uniformity(sequences)
    rc.write_csv(rc.RAW / "uniformity.csv", uniformity)
    overlaps = worker_overlap(sequences)
    rc.write_csv(rc.RAW / "worker_overlap.csv", overlaps)

    summary = rc.summarize(rows, uniformity, overlaps, exact)
    summary["campaign_design"] = {
        "source_campaigns": len(source_runs),
        "reported_trial_rows": len(rows),
        "repetitions": rc.REPETITIONS,
        "domains": len(rc.DOMAINS),
        "methods": len(rc.METHODS),
        "budget_policy": "unique capped prefixes of one maximum-budget campaign",
    }
    (rc.PROCESSED / "summary.json").write_text(
        json.dumps(summary, indent=2, allow_nan=True) + "\n", encoding="utf-8"
    )

    capabilities = [
        {"method": "pdrs", "exact_enumeration": True, "random_access": True, "uniform_objects": True, "without_replacement": True, "coordinated_partition": True, "shrinking": False, "recursive_unbounded": False},
        {"method": "feat", "exact_enumeration": True, "random_access": True, "uniform_objects": True, "without_replacement": True, "coordinated_partition": True, "shrinking": False, "recursive_unbounded": True},
        {"method": "smallcheck", "exact_enumeration": True, "random_access": False, "uniform_objects": False, "without_replacement": True, "coordinated_partition": True, "shrinking": False, "recursive_unbounded": True},
        {"method": "hypothesis", "exact_enumeration": False, "random_access": False, "uniform_objects": False, "without_replacement": False, "coordinated_partition": False, "shrinking": True, "recursive_unbounded": True},
        {"method": "grammarinator", "exact_enumeration": False, "random_access": False, "uniform_objects": False, "without_replacement": True, "coordinated_partition": False, "shrinking": False, "recursive_unbounded": True},
        {"method": "combol", "exact_enumeration": False, "random_access": False, "uniform_objects": True, "without_replacement": False, "coordinated_partition": False, "shrinking": False, "recursive_unbounded": True},
    ]
    rc.write_csv(rc.PROCESSED / "capabilities.csv", capabilities)
    rc.plot(rows, uniformity, overlaps, exact)
    print(json.dumps(summary, indent=2))


def verify() -> None:
    summary = json.loads((rc.PROCESSED / "summary.json").read_text(encoding="utf-8"))
    if set(summary["methods"]) != set(rc.METHODS):
        raise AssertionError("missing comparison method")

    with (rc.RAW / "exact_enumeration.csv").open(encoding="utf-8") as handle:
        exact = list(csv.DictReader(handle))
    for method in ("pdrs", "feat", "smallcheck"):
        method_rows = [row for row in exact if row["method"] == method]
        if len(method_rows) != len(rc.DOMAINS) or not all(
            row["complete"] == "True" for row in method_rows
        ):
            raise AssertionError(f"incomplete exact evidence for {method}")

    with (rc.RAW / "generation_runs.csv").open(encoding="utf-8") as handle:
        runs = list(csv.DictReader(handle))
    expected = (
        len(rc.METHODS)
        * rc.REPETITIONS
        * sum(len(budgets(domain)) for domain in rc.DOMAINS)
    )
    if len(runs) != expected:
        raise AssertionError(f"expected {expected} generation rows, got {len(runs)}")
    if any(float(row["validity_rate"]) != 1.0 for row in runs):
        raise AssertionError("at least one method emitted an invalid object")

    with (rc.RAW / "source_campaigns.csv").open(encoding="utf-8") as handle:
        source_runs = list(csv.DictReader(handle))
    source_expected = len(rc.METHODS) * len(rc.DOMAINS) * rc.REPETITIONS
    if len(source_runs) != source_expected:
        raise AssertionError(
            f"expected {source_expected} source campaigns, got {len(source_runs)}"
        )

    figures = list(rc.FIGURES.glob("*.svg"))
    if len(figures) < 7:
        raise AssertionError("missing comparison figures")
    print(
        f"Verified {len(runs)} matched rows, {len(source_runs)} source campaigns, "
        f"{len(exact)} exact rows, and {len(figures)} SVG figures."
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("run", "verify"))
    args = parser.parse_args()
    {"run": run, "verify": verify}[args.command]()


if __name__ == "__main__":
    main()
