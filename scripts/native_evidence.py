from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
import subprocess
import time
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = [
    "administrative",
    "ai_actions",
    "calendar",
    "compiler_ast",
    "fuzz_target",
    "permit",
    "telecom",
]


def canonical_token(token: str | int) -> str:
    if isinstance(token, bool):
        raise TypeError("boolean is not a PDRS integer token")
    if isinstance(token, int):
        return f"I:{token}"
    if any(character in token for character in "|\t\r\n"):
        raise ValueError(f"native IR requires safe choice labels, got {token!r}")
    return f"S:{token}"


def canonical_tokens(tokens: Iterable[str | int]) -> str:
    return "|".join(canonical_token(token) for token in tokens)


def load_compiled(path: Path):
    import sys

    sys.path.insert(0, str(ROOT / "src"))
    from pdrs import load_schema

    return load_schema(path)


def export_ir(document: dict[str, Any], path: Path) -> None:
    lines = [
        "PDRS_IR_V1",
        f"name\t{document.get('name', path.stem)}",
        f"version\t{document.get('version', '0')}",
        f"root\t{document['root']}",
    ]
    for name, raw in document["nodes"].items():
        kind = raw["type"]
        if kind == "terminal":
            lines.append(f"node\tT\t{name}")
        elif kind == "choice":
            fields = ["node", "C", name, str(raw.get("field", name)), str(len(raw["branches"]))]
            for branch in raw["branches"]:
                value = str(branch["value"])
                if any(character in value for character in "|\t\r\n"):
                    raise ValueError(f"unsafe choice label {value!r}")
                fields.extend([value, str(branch["target"])])
            lines.append("\t".join(fields))
        elif kind == "range":
            lines.append(
                "\t".join(
                    [
                        "node",
                        "R",
                        name,
                        str(raw.get("field", name)),
                        str(raw["start"]),
                        str(raw["stop"]),
                        str(raw["target"]),
                    ]
                )
            )
        else:
            raise ValueError(f"unsupported native node type {kind!r}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def deterministic_ranks(name: str, count: int, target: int = 2048) -> list[int]:
    if count <= target:
        return list(range(count))
    ranks = {0, 1, count // 4, count // 2, (3 * count) // 4, count - 2, count - 1}
    seed = int.from_bytes(hashlib.sha256(name.encode("utf-8")).digest()[:8], "big")
    rng = random.Random(seed)
    while len(ranks) < target:
        ranks.add(rng.randrange(count))
    return sorted(ranks)


def prepare(output: Path) -> None:
    ir_dir = output / "irs"
    ranks_dir = output / "ranks"
    ir_dir.mkdir(parents=True, exist_ok=True)
    ranks_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for stem in SCHEMAS:
        schema_path = ROOT / "schemas" / f"{stem}.json"
        document = json.loads(schema_path.read_text(encoding="utf-8"))
        compiled = load_compiled(schema_path)
        ir_path = ir_dir / f"{stem}.pdrs"
        ranks_path = ranks_dir / f"{stem}.txt"
        export_ir(document, ir_path)
        ranks = deterministic_ranks(stem, compiled.count)
        ranks_path.write_text("".join(f"{rank}\n" for rank in ranks), encoding="utf-8")
        manifest.append(
            {
                "schema": stem,
                "name": compiled.name,
                "count": compiled.count,
                "depth": compiled.depth,
                "canonical_hash": compiled.canonical_hash,
                "ir": str(ir_path.relative_to(ROOT)),
                "ranks": str(ranks_path.relative_to(ROOT)),
                "vector_count": len(ranks),
            }
        )
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def run_json(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(command, check=True, text=True, capture_output=True)
    return json.loads(completed.stdout.strip())


def run_vectors(binary: Path, ir: Path, ranks: Path) -> dict[int, str]:
    completed = subprocess.run(
        [str(binary), "vectors", str(ir), str(ranks)],
        check=True,
        text=True,
        capture_output=True,
    )
    output: dict[int, str] = {}
    for line in completed.stdout.splitlines():
        rank_text, token_text = line.split("\t", 1)
        output[int(rank_text)] = token_text
    return output


def python_benchmark(compiled, iterations: int) -> tuple[float, float]:
    sample_count = min(compiled.count, 4096)
    state = 0x9E3779B97F4A7C15
    samples = []
    for _ in range(sample_count):
        state = (state * 6364136223846793005 + 1442695040888963407) & ((1 << 64) - 1)
        samples.append(compiled.unrank(state % compiled.count))
    sink = 0
    started = time.perf_counter_ns()
    for index in range(iterations):
        sink ^= compiled.rank(samples[index % sample_count])
    rank_ns = (time.perf_counter_ns() - started) / iterations
    started = time.perf_counter_ns()
    for index in range(iterations):
        rank = ((index * 11400714819323198485) & ((1 << 64) - 1)) % compiled.count
        sink ^= len(compiled.unrank(rank))
    unrank_ns = (time.perf_counter_ns() - started) / iterations
    if sink == -1:
        raise AssertionError("unreachable benchmark guard")
    return rank_ns, unrank_ns


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def plot_results(performance_rows: list[dict[str, Any]], figures: Path) -> None:
    import matplotlib.pyplot as plt

    figures.mkdir(parents=True, exist_ok=True)
    languages = ["python", "c", "rust"]
    schemas = SCHEMAS
    lookup = {(row["language"], row["schema"]): row for row in performance_rows}
    for operation in ["rank", "unrank"]:
        x = list(range(len(schemas)))
        width = 0.25
        fig, ax = plt.subplots(figsize=(11, 5.5))
        for language_index, language in enumerate(languages):
            values = [float(lookup[(language, schema)][f"{operation}_ns"]) / 1000.0 for schema in schemas]
            positions = [value + (language_index - 1) * width for value in x]
            ax.bar(positions, values, width=width, label=language)
        ax.set_xticks(x, [schema.replace("_", "\n") for schema in schemas])
        ax.set_ylabel("microseconds per operation")
        ax.set_title(f"PDRS {operation} latency by implementation")
        ax.legend()
        fig.tight_layout()
        for suffix in ["svg", "png"]:
            fig.savefig(figures / f"native_{operation}_runtime.{suffix}", dpi=180)
        plt.close(fig)

    speedup_rows = []
    for schema in schemas:
        for language in ["c", "rust"]:
            speedup_rows.append(
                (
                    f"{language}:{schema}",
                    float(lookup[("python", schema)]["rank_ns"]) / float(lookup[(language, schema)]["rank_ns"]),
                )
            )
    fig, ax = plt.subplots(figsize=(12, 5.5))
    labels = [label for label, _ in speedup_rows]
    values = [value for _, value in speedup_rows]
    ax.bar(range(len(values)), values)
    ax.set_xticks(range(len(values)), labels, rotation=55, ha="right")
    ax.set_ylabel("Python rank latency / native rank latency")
    ax.set_title("Native PDRS rank speedup over Python reference")
    fig.tight_layout()
    for suffix in ["svg", "png"]:
        fig.savefig(figures / f"native_rank_speedup.{suffix}", dpi=180)
    plt.close(fig)


def execute(c_binary: Path, rust_binary: Path, generated: Path, iterations: int) -> None:
    manifest = json.loads((generated / "manifest.json").read_text(encoding="utf-8"))
    conformance_rows: list[dict[str, Any]] = []
    performance_rows: list[dict[str, Any]] = []
    for entry in manifest:
        stem = entry["schema"]
        schema_path = ROOT / "schemas" / f"{stem}.json"
        ir_path = ROOT / entry["ir"]
        ranks_path = ROOT / entry["ranks"]
        compiled = load_compiled(schema_path)
        ranks = [int(line) for line in ranks_path.read_text(encoding="utf-8").splitlines() if line]
        expected = {rank: canonical_tokens(compiled.unrank(rank)) for rank in ranks}
        for language, binary in [("c", c_binary), ("rust", rust_binary)]:
            verification = run_json([str(binary), "verify", str(ir_path)])
            actual = run_vectors(binary, ir_path, ranks_path)
            mismatches = sum(actual.get(rank) != value for rank, value in expected.items())
            missing = len(set(expected) - set(actual))
            failures = int(verification["failures"]) + mismatches + missing
            conformance_rows.append(
                {
                    "language": language,
                    "schema": stem,
                    "domain": compiled.count,
                    "exhaustive_roundtrips": verification["checked"],
                    "sample_vectors": len(expected),
                    "vector_mismatches": mismatches,
                    "missing_vectors": missing,
                    "failures": failures,
                }
            )
            benchmark = run_json([str(binary), "bench", str(ir_path), str(iterations)])
            performance_rows.append(
                {
                    "language": language,
                    "schema": stem,
                    "domain": compiled.count,
                    "iterations": iterations,
                    "rank_ns": benchmark["rank_ns"],
                    "unrank_ns": benchmark["unrank_ns"],
                }
            )
        python_rank, python_unrank = python_benchmark(compiled, iterations)
        performance_rows.append(
            {
                "language": "python",
                "schema": stem,
                "domain": compiled.count,
                "iterations": iterations,
                "rank_ns": python_rank,
                "unrank_ns": python_unrank,
            }
        )
    raw = ROOT / "results" / "raw"
    processed = ROOT / "results" / "processed"
    figures = ROOT / "results" / "figures"
    write_csv(raw / "native_conformance.csv", conformance_rows)
    write_csv(raw / "native_performance.csv", performance_rows)
    lookup = {(row["language"], row["schema"]): row for row in performance_rows}
    c_rank_speedups = [
        float(lookup[("python", schema)]["rank_ns"]) / float(lookup[("c", schema)]["rank_ns"])
        for schema in SCHEMAS
    ]
    rust_rank_speedups = [
        float(lookup[("python", schema)]["rank_ns"]) / float(lookup[("rust", schema)]["rank_ns"])
        for schema in SCHEMAS
    ]
    c_unrank_speedups = [
        float(lookup[("python", schema)]["unrank_ns"]) / float(lookup[("c", schema)]["unrank_ns"])
        for schema in SCHEMAS
    ]
    rust_unrank_speedups = [
        float(lookup[("python", schema)]["unrank_ns"]) / float(lookup[("rust", schema)]["unrank_ns"])
        for schema in SCHEMAS
    ]
    summary = {
        "schemas": len(SCHEMAS),
        "languages": ["python", "c", "rust"],
        "native_exhaustive_roundtrips": sum(int(row["exhaustive_roundtrips"]) for row in conformance_rows),
        "cross_language_vectors": sum(int(row["sample_vectors"]) for row in conformance_rows),
        "conformance_failures": sum(int(row["failures"]) for row in conformance_rows),
        "median_c_rank_speedup": statistics.median(c_rank_speedups),
        "median_rust_rank_speedup": statistics.median(rust_rank_speedups),
        "median_c_unrank_speedup": statistics.median(c_unrank_speedups),
        "median_rust_unrank_speedup": statistics.median(rust_unrank_speedups),
        "benchmark_iterations_per_schema_language": iterations,
        "limitations": [
            "native engines consume the canonical finite PDRS IR generated from validated JSON schemas",
            "native cardinalities are currently limited to unsigned 64-bit domains",
            "runtime results are GitHub-runner and compiler dependent",
        ],
    }
    (processed / "stage_native.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    summary_rows = [
        {"metric": key, "value": value}
        for key, value in summary.items()
        if isinstance(value, (int, float))
    ]
    write_csv(processed / "native_summary.csv", summary_rows)
    plot_results(performance_rows, figures)
    if summary["conformance_failures"] != 0:
        raise SystemExit(f"native conformance failed: {summary['conformance_failures']}")
    print(json.dumps(summary, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--output", type=Path, default=ROOT / "native" / "generated")
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--c", type=Path, required=True)
    run_parser.add_argument("--rust", type=Path, required=True)
    run_parser.add_argument("--generated", type=Path, default=ROOT / "native" / "generated")
    run_parser.add_argument("--iterations", type=int, default=200_000)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.output)
    else:
        execute(args.c, args.rust, args.generated, args.iterations)


if __name__ == "__main__":
    main()
