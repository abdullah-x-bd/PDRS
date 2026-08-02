from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "results" / "raw"
PROCESSED = ROOT / "results" / "processed"
FIGURES = ROOT / "results" / "figures"

ORDER = [
    "correctness",
    "density",
    "runtime",
    "uniformity",
    "fuzzing",
    "schema_evolution",
    "fault_propagation",
    "scalability_and_timing",
    "crypto_adapter",
    "native",
]


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "sha256"])
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    summary = {
        name: json.loads((PROCESSED / f"stage_{name}.json").read_text(encoding="utf-8"))
        for name in ORDER
    }
    (PROCESSED / "experiment_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# Generated experimental evidence summary",
        "",
        "Generated from isolated experiment stages. Runtime and timing values are environment-dependent; all other committed results are seed-controlled.",
        "",
    ]
    for name in ORDER:
        lines.extend(
            [
                f"## {name.replace('_', ' ').title()}",
                "",
                "```json",
                json.dumps(summary[name], indent=2),
                "```",
                "",
            ]
        )
    (PROCESSED / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")

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


if __name__ == "__main__":
    main()
