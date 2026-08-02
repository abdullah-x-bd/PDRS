from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
import math
from pathlib import Path
import random
import re
import statistics
import subprocess
import sys
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import chisquare

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
HERE = Path(__file__).resolve().parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from pdrs import CompiledSchema
from corpus import DOMAINS, Domain, parse_line

SEED = 20260802
RAW = ROOT / "results" / "sota" / "raw"
PROCESSED = ROOT / "results" / "sota" / "processed"
FIGURES = ROOT / "results" / "sota" / "figures"
GENERATED = HERE / "generated"
GRAMMARS = HERE / "grammars"
HASKELL_RESULTS = ROOT / "results" / "sota" / "haskell"
METHODS = ("pdrs", "feat", "smallcheck", "hypothesis", "grammarinator", "combol")
BUDGETS = (100, 500, 1000)
REPETITIONS = 20


def ensure_dirs() -> None:
    for path in (RAW, PROCESSED, FIGURES, GENERATED, GRAMMARS, HASKELL_RESULTS):
        path.mkdir(parents=True, exist_ok=True)


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"no rows for {path}")
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def camel(name: str) -> str:
    return "".join(part.capitalize() for part in name.split("_"))


def prepare() -> None:
    ensure_dirs()
    schema_dir = HERE / "schemas"
    schema_dir.mkdir(exist_ok=True)
    manifest = []
    for domain in DOMAINS:
        (schema_dir / f"{domain.name}.json").write_text(
            json.dumps(domain.pdrs_schema(), indent=2) + "\n", encoding="utf-8"
        )
        grammar_name = camel(domain.name)
        alternatives = []
        for branch, widths in enumerate(domain.branches):
            pieces = [f"'b{branch},'"]
            for index, width in enumerate(widths):
                if index:
                    pieces.append("','")
                pieces.append(f"v{width}")
            alternatives.append(" ".join(pieces))
        rules = [
            f"grammar {grammar_name};",
            "",
            "start: object '\\n';",
            "object: " + "\n      | ".join(alternatives) + ";",
        ]
        for width in sorted({width for branch in domain.branches for width in branch}):
            rules.append(f"v{width}: " + " | ".join(f"'{value}'" for value in range(width)) + ";")
        rules.append("")
        (GRAMMARS / f"{grammar_name}.g4").write_text("\n".join(rules), encoding="utf-8")
        manifest.append({
            "name": domain.name,
            "count": domain.count,
            "branch_sizes": domain.branch_sizes,
            "max_fields": domain.max_fields,
            "grammar": grammar_name,
        })
    (HERE / "corpus_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def load_haskell(method: str, domain: Domain) -> tuple[list[int], float]:
    path = HASKELL_RESULTS / f"{method}_{domain.name}.txt"
    lines = path.read_text(encoding="utf-8").splitlines()
    elapsed = 0
    values: list[int] = []
    for line in lines:
        if line.startswith("#elapsed_picoseconds="):
            elapsed = int(line.split("=", 1)[1])
        elif line and not line.startswith("#"):
            values.append(int(line))
    return values, elapsed / 1e12


def pdrs_sequence(domain: Domain, budget: int, seed: int) -> tuple[list[int], float]:
    schema = CompiledSchema(domain.pdrs_schema())
    rng = random.Random(seed)
    start = time.perf_counter()
    ranks = rng.sample(range(domain.count), k=budget)
    values = [schema.unrank(rank) for rank in ranks]
    recovered = [schema.rank(value) for value in values]
    return recovered, time.perf_counter() - start


def hypothesis_strategy(domain: Domain):
    from hypothesis import strategies as st
    alternatives = []
    for branch, widths in enumerate(domain.branches):
        fields = [st.integers(min_value=0, max_value=width - 1) for width in widths]
        alternatives.append(st.tuples(*fields).map(lambda values, branch=branch: domain.rank(branch, values)))
    return st.one_of(*alternatives)


def hypothesis_sequence(domain: Domain, budget: int, seed_value: int) -> tuple[list[int], float]:
    from hypothesis import HealthCheck, Phase, given, seed, settings
    collected: list[int] = []
    strategy = hypothesis_strategy(domain)

    def receive(value: int) -> None:
        collected.append(value)

    test = given(strategy)(receive)
    test = settings(
        max_examples=budget,
        database=None,
        deadline=None,
        phases=(Phase.generate,),
        suppress_health_check=tuple(HealthCheck),
    )(test)
    test = seed(seed_value)(test)
    start = time.perf_counter()
    test()
    return collected, time.perf_counter() - start


def grammarinator_sequence(domain: Domain, budget: int, seed_value: int) -> tuple[list[int], float]:
    grammar_name = camel(domain.name)
    class_ref = f"{grammar_name}Generator.{grammar_name}Generator"
    command = [
        "grammarinator-generate", class_ref, "-r", "start", "-d", "20",
        "--max-tokens", "32", "--stdout", "-n", str(budget),
        "--memo-size", str(budget), "--unique-attempts", "1000",
        "--random-seed", str(seed_value), "--sys-path", str(GENERATED), "-q",
    ]
    start = time.perf_counter()
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    elapsed = time.perf_counter() - start
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    ranks = [parse_line(domain, line) for line in lines]
    if len(ranks) != budget:
        raise RuntimeError(
            f"Grammarinator returned {len(ranks)} objects for {domain.name}, expected {budget}. "
            f"stderr={completed.stderr[-1000:]}"
        )
    return ranks, elapsed


_ATOM_RE = re.compile(r"\b(?:r(?P<branch>\d+)|q(?P<qb>\d+)x(?P<pos>\d+)v(?P<value>\d+)|dummy)\b")


def combol_spec(domain: Domain) -> tuple[str, dict[str, float]]:
    terms = []
    atoms: set[str] = {"dummy"}
    for branch, widths in enumerate(domain.branches):
        factors = [f"r{branch}"]
        atoms.add(f"r{branch}")
        for position, width in enumerate(widths):
            choices = []
            for value in range(width):
                atom = f"q{branch}x{position}v{value}"
                atoms.add(atom)
                choices.append(atom)
            factors.append("(" + " + ".join(choices) + ")")
        factors.extend(["dummy"] * (domain.max_fields - len(widths)))
        terms.append("(" + " * ".join(factors) + ")")
    return "D = " + " + ".join(terms), {atom: 0.25 for atom in sorted(atoms)}


def parse_combol(domain: Domain, sampled) -> int:
    text = repr(sampled)
    branch: int | None = None
    values: dict[int, int] = {}
    for match in _ATOM_RE.finditer(text):
        if match.group("branch") is not None:
            branch = int(match.group("branch"))
        elif match.group("qb") is not None:
            qb = int(match.group("qb"))
            if branch is not None and qb != branch:
                raise ValueError(f"inconsistent CombOL branch in {text}")
            branch = qb
            values[int(match.group("pos"))] = int(match.group("value"))
    if branch is None:
        raise ValueError(f"could not parse CombOL sample {text!r}")
    ordered = tuple(values[position] for position in range(len(domain.branches[branch])))
    return domain.rank(branch, ordered)


def combol_sequence(domain: Domain, budget: int, seed_value: int) -> tuple[list[int], float]:
    import combol
    specification, parameters = combol_spec(domain)
    cls = combol.parse(specification)
    sampler = cls.sampler(parameters)
    start = time.perf_counter()
    ranks = [parse_combol(domain, sampler.sample()) for _ in range(budget)]
    return ranks, time.perf_counter() - start


def bug_sets(domain: Domain) -> dict[str, set[int]]:
    rng = random.Random(SEED + domain.count)
    uniform = set(rng.sample(range(domain.count), k=min(32, domain.count)))
    sizes = domain.branch_sizes
    rare_branch = min(range(len(sizes)), key=lambda index: sizes[index])
    offset = sum(sizes[:rare_branch])
    rare = set(range(offset, offset + min(32, sizes[rare_branch])))
    boundary = set(sorted(domain.boundaries())[:32])
    start = max(0, min(domain.count - 32, (3 * domain.count) // 4))
    clustered = set(range(start, min(domain.count, start + 32)))
    interaction = set()
    for rank in range(domain.count):
        branch, values = domain.unrank(rank)
        weighted = branch + sum((index + 3) * value for index, value in enumerate(values))
        if weighted % 37 == 0:
            interaction.add(rank)
            if len(interaction) == 32:
                break
    return {"uniform": uniform, "rare_branch": rare, "boundary": boundary, "clustered": clustered, "interaction": interaction}


def assess(method: str, domain: Domain, sequence: list[int], elapsed: float, repetition: int, budget: int) -> dict:
    valid = [rank for rank in sequence if 0 <= rank < domain.count]
    unique = set(valid)
    branches = {domain.branch_of_rank(rank) for rank in unique}
    row = {
        "method": method,
        "domain": domain.name,
        "repetition": repetition,
        "budget": budget,
        "produced": len(sequence),
        "valid": len(valid),
        "validity_rate": len(valid) / len(sequence) if sequence else 0.0,
        "unique": len(unique),
        "unique_rate": len(unique) / len(valid) if valid else 0.0,
        "duplicates": len(valid) - len(unique),
        "branch_coverage": len(branches) / len(domain.branches),
        "elapsed_s": elapsed,
        "objects_per_s": len(sequence) / elapsed if elapsed > 0 else math.inf,
    }
    for scenario, bugs in bug_sets(domain).items():
        discovered: set[int] = set()
        first = None
        for index, rank in enumerate(sequence, 1):
            if rank in bugs:
                discovered.add(rank)
                if first is None:
                    first = index
        row[f"{scenario}_bugs"] = len(discovered)
        row[f"{scenario}_first"] = first if first is not None else budget + 1
    return row


def exact_evidence() -> list[dict]:
    rows = []
    for domain in DOMAINS:
        schema = CompiledSchema(domain.pdrs_schema())
        start = time.perf_counter()
        pdrs = [schema.rank(schema.unrank(rank)) for rank in range(domain.count)]
        pdrs_elapsed = time.perf_counter() - start
        feat, feat_elapsed = load_haskell("feat", domain)
        small, small_elapsed = load_haskell("smallcheck", domain)
        for method, sequence, elapsed in (("pdrs", pdrs, pdrs_elapsed), ("feat", feat, feat_elapsed), ("smallcheck", small, small_elapsed)):
            rows.append({
                "method": method,
                "domain": domain.name,
                "domain_size": domain.count,
                "produced": len(sequence),
                "unique": len(set(sequence)),
                "complete": set(sequence) == set(range(domain.count)),
                "elapsed_s": elapsed,
                "objects_per_s": len(sequence) / elapsed if elapsed else math.inf,
                "supports_random_access": method in {"pdrs", "feat"},
                "supports_exact_partitions": True,
            })
    return rows


def method_sequence(method: str, domain: Domain, budget: int, repetition: int, feat_all: list[int], small_all: list[int]) -> tuple[list[int], float]:
    seed_value = SEED + repetition * 1009 + domain.count
    if method == "pdrs":
        return pdrs_sequence(domain, budget, seed_value)
    if method == "feat":
        rng = random.Random(seed_value)
        start = time.perf_counter()
        sequence = rng.sample(feat_all, k=budget)
        return sequence, time.perf_counter() - start
    if method == "smallcheck":
        start = time.perf_counter()
        sequence = small_all[:budget]
        return sequence, time.perf_counter() - start
    if method == "hypothesis":
        return hypothesis_sequence(domain, budget, seed_value)
    if method == "grammarinator":
        return grammarinator_sequence(domain, budget, seed_value)
    if method == "combol":
        return combol_sequence(domain, budget, seed_value)
    raise KeyError(method)


def aggregate_uniformity(run_sequences: dict[tuple[str, str, int, int], list[int]]) -> list[dict]:
    rows = []
    for domain in DOMAINS:
        for requested_budget in BUDGETS:
            budget = min(requested_budget, domain.count)
            for method in METHODS:
                combined = []
                for repetition in range(REPETITIONS):
                    combined.extend(run_sequences[(method, domain.name, budget, repetition)])
                observed = np.bincount(combined, minlength=domain.count).astype(float)
                expected = np.full(domain.count, len(combined) / domain.count)
                tv = 0.5 * float(np.abs(observed / len(combined) - 1 / domain.count).sum())
                branch_observed = np.zeros(len(domain.branches))
                for rank, count in enumerate(observed):
                    branch_observed[domain.branch_of_rank(rank)] += count
                branch_expected = np.asarray(domain.branch_sizes, dtype=float) / domain.count
                branch_tv = 0.5 * float(np.abs(branch_observed / len(combined) - branch_expected).sum())
                p_value = math.nan
                if expected.min() >= 5:
                    _, p_value = chisquare(observed, expected)
                rows.append({
                    "method": method,
                    "domain": domain.name,
                    "budget": budget,
                    "samples": len(combined),
                    "object_total_variation": tv,
                    "branch_total_variation": branch_tv,
                    "chi_square_p": p_value,
                })
    return rows


def worker_overlap(run_sequences: dict[tuple[str, str, int, int], list[int]]) -> list[dict]:
    rows = []
    for domain in DOMAINS:
        budget = min(500, max(1, domain.count // 4))
        sequence_budget = min(500, domain.count)
        feat, _ = load_haskell("feat", domain)
        small, _ = load_haskell("smallcheck", domain)
        coordinated = {
            "pdrs": [set(range((worker * domain.count) // 4, ((worker + 1) * domain.count) // 4)) for worker in range(4)],
            "feat": [set(feat[worker::4]) for worker in range(4)],
            "smallcheck": [set(small[worker::4]) for worker in range(4)],
        }
        for method in METHODS:
            if method in coordinated:
                groups = [set(list(group)[:budget]) for group in coordinated[method]]
            else:
                groups = [set(run_sequences[(method, domain.name, sequence_budget, worker)]) for worker in range(4)]
            total = sum(len(group) for group in groups)
            union = len(set().union(*groups))
            rows.append({
                "method": method,
                "domain": domain.name,
                "workers": 4,
                "budget_per_worker": budget,
                "total_unique_worker_outputs": total,
                "union": union,
                "overlap_fraction": (total - union) / total if total else 0.0,
            })
    return rows


def summarize(rows: list[dict], uniformity: list[dict], overlaps: list[dict], exact: list[dict]) -> dict:
    summary = {"methods": {}, "domains": [domain.name for domain in DOMAINS]}
    for method in METHODS:
        subset = [row for row in rows if row["method"] == method]
        uni = [row for row in uniformity if row["method"] == method]
        ov = [row for row in overlaps if row["method"] == method]
        exact_rows = [row for row in exact if row["method"] == method]
        summary["methods"][method] = {
            "median_unique_rate": statistics.median(row["unique_rate"] for row in subset),
            "median_validity_rate": statistics.median(row["validity_rate"] for row in subset),
            "median_branch_tv": statistics.median(row["branch_total_variation"] for row in uni),
            "median_worker_overlap": statistics.median(row["overlap_fraction"] for row in ov),
            "median_pipeline_objects_per_s": statistics.median(row["objects_per_s"] for row in subset),
            "uniform_bug_median": statistics.median(row["uniform_bugs"] for row in subset),
            "rare_bug_median": statistics.median(row["rare_branch_bugs"] for row in subset),
            "boundary_bug_median": statistics.median(row["boundary_bugs"] for row in subset),
            "exact_complete_domains": sum(bool(row["complete"]) for row in exact_rows),
            "exact_domains_tested": len(exact_rows),
        }
    return summary


def plot(rows: list[dict], uniformity: list[dict], overlaps: list[dict], exact: list[dict]) -> None:
    labels = list(METHODS)
    display = {"pdrs": "PDRS", "feat": "Feat", "smallcheck": "SmallCheck", "hypothesis": "Hypothesis", "grammarinator": "Grammarinator", "combol": "CombOL"}
    max_budget_rows = []
    for method in METHODS:
        subset = []
        for domain in DOMAINS:
            budget = min(max(BUDGETS), domain.count)
            subset.extend(row for row in rows if row["method"] == method and row["domain"] == domain.name and row["budget"] == budget)
        max_budget_rows.append(subset)

    def bar_metric(filename: str, title: str, ylabel: str, key: str) -> None:
        medians = [statistics.median(row[key] for row in subset) for subset in max_budget_rows]
        plt.figure(figsize=(10, 5))
        plt.bar(np.arange(len(labels)), medians)
        plt.xticks(np.arange(len(labels)), [display[label] for label in labels], rotation=20)
        plt.ylabel(ylabel)
        plt.title(title)
        plt.tight_layout()
        plt.savefig(FIGURES / f"{filename}.svg")
        plt.savefig(FIGURES / f"{filename}.png", dpi=180)
        plt.close()

    bar_metric("unique_rate", "Unique valid output rate at maximum matched budget", "Unique rate", "unique_rate")
    bar_metric("uniform_bug_discovery", "Uniformly located bugs reached", "Distinct bugs", "uniform_bugs")
    bar_metric("rare_bug_discovery", "Rare-branch bugs reached", "Distinct bugs", "rare_branch_bugs")
    bar_metric("boundary_bug_discovery", "Boundary bugs reached", "Distinct bugs", "boundary_bugs")

    plt.figure(figsize=(10, 5))
    branch_tv = [statistics.median(row["branch_total_variation"] for row in uniformity if row["method"] == method) for method in METHODS]
    plt.bar(np.arange(len(labels)), branch_tv)
    plt.xticks(np.arange(len(labels)), [display[label] for label in labels], rotation=20)
    plt.ylabel("Median branch total variation")
    plt.title("Deviation from object-uniform branch probabilities")
    plt.tight_layout()
    plt.savefig(FIGURES / "uniformity_branch_tv.svg")
    plt.savefig(FIGURES / "uniformity_branch_tv.png", dpi=180)
    plt.close()

    plt.figure(figsize=(10, 5))
    overlap_values = [statistics.median(row["overlap_fraction"] for row in overlaps if row["method"] == method) for method in METHODS]
    plt.bar(np.arange(len(labels)), overlap_values)
    plt.xticks(np.arange(len(labels)), [display[label] for label in labels], rotation=20)
    plt.ylabel("Median overlap fraction")
    plt.title("Four-worker duplicate overlap")
    plt.tight_layout()
    plt.savefig(FIGURES / "worker_overlap.svg")
    plt.savefig(FIGURES / "worker_overlap.png", dpi=180)
    plt.close()

    exact_methods = ["pdrs", "feat", "smallcheck"]
    exact_speed = [statistics.median(row["objects_per_s"] for row in exact if row["method"] == method) for method in exact_methods]
    plt.figure(figsize=(8, 5))
    plt.bar(np.arange(3), exact_speed)
    plt.xticks(np.arange(3), ["PDRS", "Feat", "SmallCheck"])
    plt.ylabel("Median objects per second")
    plt.title("Complete finite-domain enumeration throughput")
    plt.tight_layout()
    plt.savefig(FIGURES / "exact_enumeration.svg")
    plt.savefig(FIGURES / "exact_enumeration.png", dpi=180)
    plt.close()


def run() -> None:
    ensure_dirs()
    exact = exact_evidence()
    write_csv(RAW / "exact_enumeration.csv", exact)
    rows: list[dict] = []
    sequences: dict[tuple[str, str, int, int], list[int]] = {}
    for domain in DOMAINS:
        feat_all, _ = load_haskell("feat", domain)
        small_all, _ = load_haskell("smallcheck", domain)
        for requested_budget in BUDGETS:
            budget = min(requested_budget, domain.count)
            for repetition in range(REPETITIONS):
                for method in METHODS:
                    sequence, elapsed = method_sequence(method, domain, budget, repetition, feat_all, small_all)
                    sequences[(method, domain.name, budget, repetition)] = sequence
                    rows.append(assess(method, domain, sequence, elapsed, repetition, budget))
    write_csv(RAW / "generation_runs.csv", rows)
    uniformity = aggregate_uniformity(sequences)
    write_csv(RAW / "uniformity.csv", uniformity)
    overlaps = worker_overlap(sequences)
    write_csv(RAW / "worker_overlap.csv", overlaps)
    summary = summarize(rows, uniformity, overlaps, exact)
    (PROCESSED / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=True) + "\n", encoding="utf-8")
    capabilities = [
        {"method": "pdrs", "exact_enumeration": True, "random_access": True, "uniform_objects": True, "without_replacement": True, "coordinated_partition": True, "shrinking": False, "recursive_unbounded": False},
        {"method": "feat", "exact_enumeration": True, "random_access": True, "uniform_objects": True, "without_replacement": True, "coordinated_partition": True, "shrinking": False, "recursive_unbounded": True},
        {"method": "smallcheck", "exact_enumeration": True, "random_access": False, "uniform_objects": False, "without_replacement": True, "coordinated_partition": True, "shrinking": False, "recursive_unbounded": True},
        {"method": "hypothesis", "exact_enumeration": False, "random_access": False, "uniform_objects": False, "without_replacement": False, "coordinated_partition": False, "shrinking": True, "recursive_unbounded": True},
        {"method": "grammarinator", "exact_enumeration": False, "random_access": False, "uniform_objects": False, "without_replacement": True, "coordinated_partition": False, "shrinking": False, "recursive_unbounded": True},
        {"method": "combol", "exact_enumeration": False, "random_access": False, "uniform_objects": True, "without_replacement": False, "coordinated_partition": False, "shrinking": False, "recursive_unbounded": True},
    ]
    write_csv(PROCESSED / "capabilities.csv", capabilities)
    plot(rows, uniformity, overlaps, exact)
    print(json.dumps(summary, indent=2))


def verify() -> None:
    summary = json.loads((PROCESSED / "summary.json").read_text(encoding="utf-8"))
    if set(summary["methods"]) != set(METHODS):
        raise AssertionError("missing comparison method")
    with (RAW / "exact_enumeration.csv").open(encoding="utf-8") as handle:
        exact = list(csv.DictReader(handle))
    for method in ("pdrs", "feat", "smallcheck"):
        method_rows = [row for row in exact if row["method"] == method]
        if len(method_rows) != len(DOMAINS) or not all(row["complete"] == "True" for row in method_rows):
            raise AssertionError(f"incomplete exact evidence for {method}")
    with (RAW / "generation_runs.csv").open(encoding="utf-8") as handle:
        runs = list(csv.DictReader(handle))
    expected = len(METHODS) * len(DOMAINS) * len(BUDGETS) * REPETITIONS
    if len(runs) != expected:
        raise AssertionError(f"expected {expected} generation rows, got {len(runs)}")
    if any(float(row["validity_rate"]) != 1.0 for row in runs):
        raise AssertionError("at least one method emitted an invalid object")
    figures = list(FIGURES.glob("*.svg"))
    if len(figures) < 7:
        raise AssertionError("missing comparison figures")
    print(f"Verified {len(runs)} runs, {len(exact)} exact rows, and {len(figures)} SVG figures.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "run", "verify"))
    args = parser.parse_args()
    {"prepare": prepare, "run": run, "verify": verify}[args.command]()


if __name__ == "__main__":
    main()
