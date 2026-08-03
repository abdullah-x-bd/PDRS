from __future__ import annotations

import csv
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "results" / "processed"
PAPER = ROOT / "paper"


def load(name: str, default=None):
    path = PROCESSED / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def claim_audit() -> dict:
    patterns = {
        "new_theory": re.compile(r"\b(?:is|presents|introduces|creates)\s+(?:a\s+)?new theory\b", re.I),
        "revolutionary": re.compile(r"\brevolutionary\b", re.I),
        "superior_bug_finding": re.compile(r"\bsuperior bug finding\b", re.I),
        "unqualified_exact_replay": re.compile(r"\b(?:provides|guarantees|enables)\s+exact replay\b", re.I),
        "universal_optimum": re.compile(r"\b(?:is|remains)\s+universally optimal\b", re.I),
        "pareto_frontier": re.compile(r"\bpareto frontier\b", re.I),
        "unique_zero_overlap": re.compile(r"\bunique zero-overlap\b", re.I),
        "perfect_reproduction": re.compile(r"\bperfect reproduction\b", re.I),
        "unqualified_information_optimal": re.compile(r"\binformation-theoretically optimal(?:\s+(?!fixed-width|schema-relative))?\b", re.I),
    }
    files = sorted(PAPER.rglob("*.tex")) + [ROOT / "README.md"]
    hits = []
    for path in files:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for name, pattern in patterns.items():
            for match in pattern.finditer(text):
                hits.append({"file": str(path.relative_to(ROOT)), "rule": name, "text": match.group(0)})
    output = PROCESSED / "claim_audit.csv"
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["file", "rule", "text"])
        writer.writeheader(); writer.writerows(hits)
    return {"files": len(files), "prohibited_affirmative_hits": len(hits), "hits": hits}


def main() -> None:
    external = load("external_baselines.json", {"asn1_rows": 0, "asn1_roundtrip_failures": 1, "bdd_rows": 0, "bdd_count_failures": 1})
    rust = load("rust_mutation_summary.json", {"mutants": 0, "score": 0.0, "baseline_passed": False})
    score = load("completion_scorecard.json", {"checks": {}})
    audit = claim_audit()
    checks = dict(score.get("checks", {}))
    checks.update({
        "actual_asn1_per_roundtrips": external.get("asn1_rows", 0) >= 10 and external.get("asn1_roundtrip_failures") == 0,
        "actual_external_bdd_count": external.get("bdd_rows", 0) >= 5 and external.get("bdd_count_failures") == 0,
        "rust_curated_mutation": rust.get("baseline_passed") is True and float(rust.get("score", 0.0)) == 1.0,
        "claim_audit": audit["prohibited_affirmative_hits"] == 0,
        "held_out_or_historical_defect_gate": checks.get("held_out_mutation_score", False),
    })
    technical = all(checks.values())
    final = {
        "checks": checks,
        "passed": sum(bool(value) for value in checks.values()),
        "total": len(checks),
        "technical_all_passed": technical,
        "permanent_archive": {
            "doi": None,
            "status": "external-owner-action-required",
            "requirement": "A GitHub release must be archived by Zenodo and the returned DOI must resolve to that exact release.",
        },
        "strict_publication_complete": False,
        "reason": "The technical artifact can pass in CI; DOI minting is an external repository-owner action and is not fabricated.",
    }
    write_json(PROCESSED / "completion_scorecard_final.json", final)
    write_json(PROCESSED / "claim_audit_summary.json", audit)
    subprocess.run([sys.executable, str(PAPER / "generate_results_tex.py")], check=True)
    if not technical:
        failed = [name for name, value in checks.items() if not value]
        raise SystemExit("technical scorecard failures: " + ", ".join(failed))
    print(json.dumps(final, indent=2))


if __name__ == "__main__":
    main()
