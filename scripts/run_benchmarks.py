from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pdrs import CompiledSchema, load_schema
from pdrs.examples import fixed_radix_schema


def ceil_bits(n: int) -> int:
    return max(0, (n - 1).bit_length())


def row(name: str, schema: CompiledSchema, naive_bits: int, category: str) -> dict[str, str | int | float]:
    dense_bits = ceil_bits(schema.count)
    return {
        "schema": name,
        "category": category,
        "domain_size": schema.count,
        "dense_bits": dense_bits,
        "naive_bits": naive_bits,
        "bits_saved": naive_bits - dense_bits,
        "encoding_efficiency": round(dense_bits / naive_bits, 6) if naive_bits else 1.0,
        "naive_space_utilization": round(schema.count / (2 ** naive_bits), 9),
        "schema_hash": schema.canonical_hash,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="results/baseline_density.csv")
    args = parser.parse_args()

    permit = load_schema(ROOT / "schemas" / "permit.json")
    calendar = load_schema(ROOT / "schemas" / "calendar.json")
    actions = load_schema(ROOT / "schemas" / "ai_actions.json")
    clock = CompiledSchema(fixed_radix_schema("clock", [24, 60, 60]))

    rows = [
        row("permit", permit, 16, "dependent"),
        row("two-year-calendar", calendar, 14, "dependent"),
        row("ai-actions", actions, 8, "dependent"),
        row("clock", clock, 17, "fixed-mixed-radix"),
    ]

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0])
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
