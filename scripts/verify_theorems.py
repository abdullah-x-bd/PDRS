from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from pdrs import CompiledSchema
from pdrs.generators import random_tree_schema


def naive_enumerate(document: dict[str, Any], node_name: str) -> list[list[str | int]]:
    node = document["nodes"][node_name]
    kind = node["type"]
    if kind == "terminal":
        return [[]]
    if kind == "choice":
        output: list[list[str | int]] = []
        for branch in node["branches"]:
            for suffix in naive_enumerate(document, branch["target"]):
                output.append([branch["value"], *suffix])
        return output
    if kind == "range":
        output = []
        for value in range(node["start"], node["stop"] + 1):
            for suffix in naive_enumerate(document, node["target"]):
                output.append([value, *suffix])
        return output
    raise AssertionError(f"unsupported kind {kind}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schemas", type=int, default=1000)
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "processed" / "theorem_verification.json")
    args = parser.parse_args()
    total_objects = 0
    for seed in range(args.schemas):
        document = random_tree_schema(900_000 + seed, max_depth=4)
        expected = naive_enumerate(document, document["root"])
        schema = CompiledSchema(document)
        assert schema.count == len(expected)
        assert [schema.unrank(index) for index in range(schema.count)] == expected
        for index, value in enumerate(expected):
            assert schema.rank(value) == index
            assert schema.unrank(schema.rank(value)) == value
        total_objects += len(expected)
    result = {
        "schema_class": "finite acyclic choice/range/terminal trees",
        "independent_enumerator": True,
        "schemas_checked": args.schemas,
        "objects_checked": total_objects,
        "failures": 0,
        "note": "Executable exhaustive model checking complements, but does not replace, the general inductive proof in theory/proofs.md.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
