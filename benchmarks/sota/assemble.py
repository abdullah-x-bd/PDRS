from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "results" / "sota"


def version(command: list[str]) -> str:
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        return (result.stdout or result.stderr).strip()
    except Exception as exc:
        return f"unavailable: {exc}"


environment = {
    "python": sys.version,
    "platform": platform.platform(),
    "machine": platform.machine(),
    "python_packages": {
        name: importlib.metadata.version(name)
        for name in ("hypothesis", "grammarinator", "numpy", "scipy", "matplotlib")
    },
    "haskell_packages": {
        "QuickCheck": version(["ghc-pkg", "field", "QuickCheck", "version", "--simple-output"]),
        "smallcheck": version(["ghc-pkg", "field", "smallcheck", "version", "--simple-output"]),
        "testing-feat": version(["ghc-pkg", "field", "testing-feat", "version", "--simple-output"]),
    },
    "ghc": version(["ghc", "--version"]),
    "cabal": version(["cabal", "--version"]),
    "java": version(["java", "-version"]),
}
(BASE / "processed").mkdir(parents=True, exist_ok=True)
(BASE / "processed" / "environment.json").write_text(
    json.dumps(environment, indent=2) + "\n", encoding="utf-8"
)

rows = []
for path in sorted(BASE.rglob("*")):
    if not path.is_file() or path.name == "SHA256SUMS.csv":
        continue
    rows.append(
        {
            "path": path.relative_to(ROOT).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size,
        }
    )
with (BASE / "processed" / "SHA256SUMS.csv").open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=("path", "sha256", "bytes"))
    writer.writeheader()
    writer.writerows(rows)
print(f"Recorded {len(rows)} SOTA evidence files.")
