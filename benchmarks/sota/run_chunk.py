from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import time

import numpy as np

import run_comparison as rc
from corpus import DOMAINS
from pdrs import CompiledSchema


def enable_combol_compatibility() -> None:
    """Ignore CombOL's implicit neutral atom in its explicit parameter map."""
    from combol.context import Context

    original = Context._translate_str_params

    def translate(self: Context, params: dict[str, float]):
        normalized = {
            key: 1.0
            for key in params
            if key in self.variable_key_map
        }
        return original(self, normalized)

    Context._translate_str_params = translate


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
    if method == "combol":
        enable_combol_compatibility()

    feat_all, _ = rc.load_haskell("feat", domain)
    small_all, _ = rc.load_haskell("smallcheck", domain)
    rows: list[dict] = []
    sequences: dict[str, list[int]] = {}

    for requested_budget in rc.BUDGETS:
        budget = min(requested_budget, domain.count)
        for repetition in range(rc.REPETITIONS):
            seed_value = rc.SEED + repetition * 1009 + domain.count
            # CombOL may delegate randomness to either Python or NumPy depending
            # on its installed backend. Seed both before each independent run.
            if method == "combol":
                random.seed(seed_value)
                np.random.seed(seed_value % (2**32))
            sequence, elapsed = rc.method_sequence(
                method,
                domain,
                budget,
                repetition,
                feat_all,
                small_all,
            )
            sequences[f"{budget}:{repetition}"] = sequence
            rows.append(
                rc.assess(
                    method,
                    domain,
                    sequence,
                    elapsed,
                    repetition,
                    budget,
                )
            )

    payload = {
        "method": method,
        "domain": domain.name,
        "domain_size": domain.count,
        "budgets": [min(value, domain.count) for value in rc.BUDGETS],
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
        f"rows={len(rows)} samples={sum(len(value) for value in sequences.values())}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--method", required=True, choices=rc.METHODS)
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
