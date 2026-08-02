from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

import run_comparison as rc
from corpus import DOMAINS
from pdrs import CompiledSchema

SCORED_METHODS = (
    "pdrs",
    "feat",
    "smallcheck",
    "hypothesis",
    "grammarinator",
    "quickcheck",
)


def load_quickcheck(domain, repetition: int) -> tuple[list[int], float]:
    path = rc.HASKELL_RESULTS / f"quickcheck_{domain.name}_{repetition}.txt"
    lines = path.read_text(encoding="utf-8").splitlines()
    elapsed_picoseconds = 0
    values: list[int] = []
    for line in lines:
        if line.startswith("#elapsed_picoseconds="):
            elapsed_picoseconds = int(line.split("=", 1)[1])
        elif line and not line.startswith("#"):
            values.append(int(line))
    if len(values) != 1000:
        raise AssertionError(
            f"QuickCheck produced {len(values)} values for "
            f"{domain.name} repetition {repetition}, expected 1000"
        )
    return values, elapsed_picoseconds / 1e12


def exact_row(method: str, domain) -> dict | None:
    if method == "pdrs":
        schema = CompiledSchema(domain.pdrs_schema())
        start = time.perf_counter()
        sequence = [schema.rank(schema.unrank(rank)) for rank in range(domain.count)]
        elapsed = time.perf_counter() - start
    elif method in {"feat", "smallcheck"}:
        sequence, elapsed = rc.load_haskell(method, domain)
    else:
        return None
    return {
        "method": method,
        "domain": domain.name,
        "domain_size": domain.count,
        "produced": len(sequence),
        "unique": len(set(sequence)),
        "complete": set(sequence) == set(range(domain.count)),
        "elapsed_s": elapsed,
        "objects_per_s": len(sequence) / elapsed if elapsed else float("inf"),
        "supports_random_access": method in {"pdrs", "feat"},
        "supports_exact_partitions": True,
    }


def run_chunk(method: str, domain_name: str, output: Path) -> None:
    rc.ensure_dirs()
    domain = next(domain for domain in DOMAINS if domain.name == domain_name)

    feat_all, _ = rc.load_haskell("feat", domain)
    small_all, _ = rc.load_haskell("smallcheck", domain)
    rows: list[dict] = []
    sequences: dict[str, list[int]] = {}
    maximum_budget = max(min(value, domain.count) for value in rc.BUDGETS)

    for repetition in range(rc.REPETITIONS):
        if method == "quickcheck":
            full_sequence, elapsed = load_quickcheck(domain, repetition)
        else:
            full_sequence, elapsed = rc.method_sequence(
                method,
                domain,
                maximum_budget,
                repetition,
                feat_all,
                small_all,
            )
        if len(full_sequence) != maximum_budget:
            raise AssertionError(
                f"{method}/{domain.name} produced {len(full_sequence)} values, "
                f"expected {maximum_budget}"
            )
        for requested_budget in rc.BUDGETS:
            budget = min(requested_budget, domain.count)
            sequence = full_sequence[:budget]
            sequences[f"{budget}:{repetition}"] = sequence
            row = rc.assess(
                method,
                domain,
                sequence,
                elapsed,
                repetition,
                budget,
            )
            row["source_budget"] = maximum_budget
            row["source_elapsed_s"] = elapsed
            row["source_objects_per_s"] = (
                maximum_budget / elapsed if elapsed else float("inf")
            )
            rows.append(row)

    payload = {
        "method": method,
        "domain": domain.name,
        "domain_size": domain.count,
        "budgets": [min(value, domain.count) for value in rc.BUDGETS],
        "maximum_source_budget": maximum_budget,
        "repetitions": rc.REPETITIONS,
        "rows": rows,
        "sequences": sequences,
        "exact": exact_row(method, domain),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, allow_nan=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"completed method={method} domain={domain.name} "
        f"rows={len(rows)} stored_sequences={len(sequences)} "
        f"source_campaigns={rc.REPETITIONS}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--method", required=True, choices=SCORED_METHODS)
    parser.add_argument(
        "--domain",
        required=True,
        choices=tuple(domain.name for domain in DOMAINS),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run_chunk(args.method, args.domain, args.output)


if __name__ == "__main__":
    main()
