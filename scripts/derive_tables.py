from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from statistics import median

from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "results" / "raw"
PROCESSED = ROOT / "results" / "processed"


def read_csv(name: str) -> list[dict[str, str]]:
    with (RAW / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(name: str, rows: list[dict]) -> None:
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with (PROCESSED / name).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def wilson(successes: int, trials: int, alpha: float = 0.05) -> tuple[float, float]:
    if trials == 0:
        return math.nan, math.nan
    z = norm.ppf(1 - alpha / 2)
    p = successes / trials
    denominator = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / denominator
    margin = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / denominator
    return center - margin, center + margin


def main() -> None:
    density_rows = []
    for row in read_csv("density_static.csv"):
        pdrs = float(row["pdrs_fixed_bits"])
        uper = float(row["uper_subset_avg_bits"])
        protobuf = float(row["protobuf_avg_bits"])
        naive = float(row["naive_cartesian_bits"])
        density_rows.append({
            "schema": row["schema"],
            "domain": int(row["domain"]),
            "pdrs_bits": pdrs,
            "uper_subset_bits": uper,
            "uper_saving_bits": uper - pdrs,
            "uper_saving_percent": 100 * (uper - pdrs) / uper,
            "protobuf_bits": protobuf,
            "protobuf_saving_bits": protobuf - pdrs,
            "protobuf_saving_percent": 100 * (protobuf - pdrs) / protobuf,
            "naive_cartesian_bits": naive,
            "naive_saving_percent": 100 * (naive - pdrs) / naive,
        })
    write_csv("density_summary.csv", density_rows)

    fault_rows = []
    for row in read_csv("fault_propagation.csv"):
        flips = int(row["single_bit_flips"])
        valid = int(row["valid_corruptions"])
        low, high = wilson(valid, flips)
        fault_rows.append({
            **row,
            "valid_corruption_wilson_low": low,
            "valid_corruption_wilson_high": high,
        })
    write_csv("fault_summary.csv", fault_rows)

    fuzz = list(csv.DictReader((PROCESSED / "fuzzing_summary.csv").open(encoding="utf-8")))
    pdrs = next(row for row in fuzz if row["method"] == "pdrs_without_replacement")
    direct = next(row for row in fuzz if row["method"] == "direct_grammar")
    reject = next(row for row in fuzz if row["method"] == "naive_rejection")
    mutation = next(row for row in fuzz if row["method"] == "mutation")

    summary = json.loads((PROCESSED / "experiment_summary.json").read_text(encoding="utf-8"))
    headline = [
        {"metric": "Objects checked with zero rank/unrank failures", "value": summary["correctness"]["objects_checked"], "unit": "objects"},
        {"metric": "Generated schemas exhaustively checked", "value": summary["correctness"]["generated_schemas"], "unit": "schemas"},
        {"metric": "Median PDRS saving versus protobuf wire baseline", "value": summary["density"]["median_pdrs_vs_protobuf_saving_bits"], "unit": "bits/object"},
        {"metric": "Median PDRS saving versus UPER subset", "value": summary["density"]["median_pdrs_vs_uper_saving_bits"], "unit": "bits/object"},
        {"metric": "Median rank latency", "value": summary["runtime"]["median_rank_us"], "unit": "microseconds"},
        {"metric": "Maximum uniformity total variation", "value": summary["uniformity"]["max_total_variation"], "unit": "fraction"},
        {"metric": "Minimum uniformity chi-square p-value", "value": summary["uniformity"]["minimum_p_value"], "unit": "p-value"},
        {"metric": "PDRS unique valid objects per 3500 attempts", "value": pdrs["median_unique"], "unit": "objects"},
        {"metric": "Direct grammar unique valid objects per 3500 attempts", "value": direct["median_unique"], "unit": "objects"},
        {"metric": "Naive rejection valid rate", "value": reject["median_validity_rate"], "unit": "fraction"},
        {"metric": "PDRS median seeded bugs found", "value": pdrs["median_bugs_found"], "unit": "bugs"},
        {"metric": "Direct grammar median seeded bugs found", "value": direct["median_bugs_found"], "unit": "bugs"},
        {"metric": "PDRS parallel overlap", "value": summary["fuzzing"]["pdrs_parallel_overlap"], "unit": "fraction"},
        {"metric": "Direct grammar parallel overlap", "value": summary["fuzzing"]["grammar_parallel_overlap"], "unit": "fraction"},
        {"metric": "Maximum schema-evolution rank churn", "value": summary["schema_evolution"]["maximum_churn"], "unit": "fraction"},
        {"metric": "Median raw-rank valid corruption rate", "value": summary["fault_propagation"]["median_valid_corruption_fraction"], "unit": "fraction"},
        {"metric": "Resource attacks rejected", "value": summary["scalability_and_timing"]["resource_attacks_rejected"], "unit": "of 4"},
        {"metric": "Domain permutation failures", "value": summary["crypto_adapter"]["permutation_failures"], "unit": "failures"},
        {"metric": "Mean domain-permutation avalanche", "value": summary["crypto_adapter"]["mean_avalanche_fraction"], "unit": "fraction"},
    ]
    write_csv("headline_results.csv", headline)


if __name__ == "__main__":
    main()
