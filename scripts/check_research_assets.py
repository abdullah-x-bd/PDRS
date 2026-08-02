from __future__ import annotations

import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pdrs import load_schema


REQUIRED_CLAIM_COLUMNS = {
    "claim_id", "claim", "type", "supporting_artifact", "strength", "status"
}
REQUIRED_SOURCE_COLUMNS = {
    "source_id", "title", "authors", "year", "identifier", "primary_source", "status", "notes"
}


def read_header(path: Path) -> set[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        return set(next(reader))


def main() -> int:
    errors: list[str] = []
    claim_path = ROOT / "literature" / "claim_evidence_matrix.csv"
    source_path = ROOT / "literature" / "source_registry.csv"
    if not REQUIRED_CLAIM_COLUMNS.issubset(read_header(claim_path)):
        errors.append("claim evidence matrix is missing required columns")
    if not REQUIRED_SOURCE_COLUMNS.issubset(read_header(source_path)):
        errors.append("source registry is missing required columns")

    manifests = sorted((ROOT / "experiments").glob("E*/manifest.json"))
    if not manifests:
        errors.append("no experiment manifests found")
    for path in manifests:
        data = json.loads(path.read_text(encoding="utf-8"))
        for key in ("experiment_id", "claim_ids", "hypothesis", "metrics", "command"):
            if key not in data:
                errors.append(f"{path}: missing {key}")

    for path in sorted((ROOT / "schemas").glob("*.json")):
        try:
            schema = load_schema(path)
            if schema.count < 1:
                errors.append(f"{path}: empty domain")
        except Exception as exc:
            errors.append(f"{path}: {exc}")

    generated = ROOT / "results" / "baseline_density.csv"
    if not generated.exists():
        errors.append("baseline density result is missing")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"validated {len(manifests)} experiment manifests and research assets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
