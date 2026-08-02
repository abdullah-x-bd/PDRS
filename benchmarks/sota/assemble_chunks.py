from __future__ import annotations

import csv
import json
from pathlib import Path

import run_comparison as rc
from corpus import DOMAINS

ROOT = Path(__file__).resolve().parents[2]
CHUNKS = ROOT / "results" / "sota" / "chunks"

CAPABILITIES = [
    {"method": "pdrs", "exact_enumeration": True, "random_access": True, "uniform_objects": True, "without_replacement": True, "coordinated_partition": True, "shrinking": False, "recursive_unbounded": False},
    {"method": "feat", "exact_enumeration": True, "random_access": True, "uniform_objects": True, "without_replacement": True, "coordinated_partition": True, "shrinking": False, "recursive_unbounded": True},
    {"method": "smallcheck", "exact_enumeration": True, "random_access": False, "uniform_objects": False, "without_replacement": True, "coordinated_partition": True, "shrinking": False, "recursive_unbounded": True},
    {"method": "hypothesis", "exact_enumeration": False, "random_access": False, "uniform_objects": False, "without_replacement": False, "coordinated_partition": False, "shrinking": True, "recursive_unbounded": True},
    {"method": "grammarinator", "exact_enumeration": False, "random_access": False, "uniform_objects": False, "without_replacement": True, "coordinated_partition": False, "shrinking": False, "recursive_unbounded": True},
    {"method": "combol", "exact_enumeration": False, "random_access": False, "uniform_objects": True, "without_replacement": False, "coordinated_partition": False, "shrinking": False, "recursive_unbounded": True},
]


def assemble() -> None:
    rc.ensure_dirs()
    expected = {
        (method, domain.name)
        for method in rc.METHODS
        for domain in DOMAINS
    }
    payloads: dict[tuple[str, str], dict] = {}
    for path in sorted(CHUNKS.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        key = (payload["method"], payload["domain"])
        if key in payloads:
            raise AssertionError(f"duplicate comparison chunk {key}")
        payloads[key] = payload
    missing = expected - set(payloads)
    unexpected = set(payloads) - expected
    if missing or unexpected:
        raise AssertionError(
            f"comparison chunk mismatch missing={sorted(missing)} "
            f"unexpected={sorted(unexpected)}"
        )

    rows: list[dict] = []
    exact: list[dict] = []
    sequences: dict[tuple[str, str, int, int], list[int]] = {}
    for method, domain_name in sorted(expected):
        payload = payloads[(method, domain_name)]
        domain = next(domain for domain in DOMAINS if domain.name == domain_name)
        expected_rows = len(rc.BUDGETS) * rc.REPETITIONS
        if len(payload["rows"]) != expected_rows:
            raise AssertionError(
                f"{method}/{domain_name} has {len(payload['rows'])} rows, "
                f"expected {expected_rows}"
            )
        rows.extend(payload["rows"])
        if payload["exact"] is not None:
            exact.append(payload["exact"])
        for requested_budget in rc.BUDGETS:
            budget = min(requested_budget, domain.count)
            for repetition in range(rc.REPETITIONS):
                sequence_key = f"{budget}:{repetition}"
                try:
                    sequence = payload["sequences"][sequence_key]
                except KeyError as exc:
                    raise AssertionError(
                        f"missing sequence {method}/{domain_name}/{sequence_key}"
                    ) from exc
                sequences[(method, domain_name, budget, repetition)] = sequence

    expected_run_rows = (
        len(rc.METHODS)
        * len(DOMAINS)
        * len(rc.BUDGETS)
        * rc.REPETITIONS
    )
    if len(rows) != expected_run_rows:
        raise AssertionError(
            f"assembled {len(rows)} run rows, expected {expected_run_rows}"
        )
    if any(float(row["validity_rate"]) != 1.0 for row in rows):
        raise AssertionError("a comparison system emitted an invalid object")

    rc.write_csv(rc.RAW / "generation_runs.csv", rows)
    rc.write_csv(rc.RAW / "exact_enumeration.csv", exact)
    uniformity = rc.aggregate_uniformity(sequences)
    rc.write_csv(rc.RAW / "uniformity.csv", uniformity)
    overlaps = rc.worker_overlap(sequences)
    rc.write_csv(rc.RAW / "worker_overlap.csv", overlaps)
    summary = rc.summarize(rows, uniformity, overlaps, exact)
    (rc.PROCESSED / "summary.json").write_text(
        json.dumps(summary, indent=2, allow_nan=True) + "\n",
        encoding="utf-8",
    )
    rc.write_csv(rc.PROCESSED / "capabilities.csv", CAPABILITIES)
    rc.plot(rows, uniformity, overlaps, exact)

    audit_rows = []
    for (method, domain), payload in sorted(payloads.items()):
        audit_rows.append(
            {
                "method": method,
                "domain": domain,
                "domain_size": payload["domain_size"],
                "run_rows": len(payload["rows"]),
                "stored_sequences": len(payload["sequences"]),
                "stored_samples": sum(
                    len(sequence)
                    for sequence in payload["sequences"].values()
                ),
                "exact_evidence": payload["exact"] is not None,
            }
        )
    rc.write_csv(rc.PROCESSED / "chunk_audit.csv", audit_rows)
    print(json.dumps(summary, indent=2, allow_nan=True))
    print(
        f"assembled {len(payloads)} chunks, {len(rows)} matched runs, "
        f"{len(exact)} exact-enumeration rows"
    )


if __name__ == "__main__":
    assemble()
