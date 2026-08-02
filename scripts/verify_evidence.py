from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "results" / "processed"


def main() -> None:
    checksum_path = PROCESSED / "SHA256SUMS.csv"
    rows = list(csv.DictReader(checksum_path.open(encoding="utf-8")))
    failures: list[str] = []
    for row in rows:
        path = ROOT / row["path"]
        if not path.is_file():
            failures.append(f"missing {row['path']}")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != row["sha256"]:
            failures.append(f"hash mismatch {row['path']}")

    summary = json.loads((PROCESSED / "experiment_summary.json").read_text(encoding="utf-8"))
    assertions = {
        "correctness failures": summary["correctness"]["failures"] == 0,
        "permutation failures": summary["crypto_adapter"]["permutation_failures"] == 0,
        "tamper detection": summary["crypto_adapter"]["minimum_tamper_detection"] == 1.0,
        "resource rejection": summary["scalability_and_timing"]["resource_attacks_rejected"] == summary["scalability_and_timing"]["resource_attacks"],
        "partition overlap": summary["fuzzing"]["pdrs_parallel_overlap"] == 0.0,
        "uniformity p-value": summary["uniformity"]["minimum_p_value"] > 0.01,
    }
    failures.extend(name for name, passed in assertions.items() if not passed)

    pngs = sorted((ROOT / "results" / "figures").glob("*.png"))
    svgs = sorted((ROOT / "results" / "figures").glob("*.svg"))
    if len(svgs) != 11:
        failures.append(f"expected 11 committed SVG figures, found {len(svgs)}")
    if len(pngs) not in (0, 11):
        failures.append(f"expected either 0 or 11 generated PNG figures, found {len(pngs)}")

    if failures:
        raise SystemExit("Evidence verification failed:\n- " + "\n- ".join(failures))
    print(f"Verified {len(rows)} evidence files, {len(svgs)} committed SVG figures, and all critical invariants.")


if __name__ == "__main__":
    main()
