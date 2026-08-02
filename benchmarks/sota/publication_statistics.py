from __future__ import annotations

import csv
import json
from pathlib import Path
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import rankdata, wilcoxon

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "results" / "sota"
RAW = BASE / "raw"
PROCESSED = BASE / "processed"
FIGURES = BASE / "figures"
SEED = 20260802
COMPARATORS = ("feat", "smallcheck", "hypothesis", "grammarinator", "quickcheck")
DISPLAY = {
    "feat": "Feat",
    "smallcheck": "SmallCheck",
    "hypothesis": "Hypothesis",
    "grammarinator": "Grammarinator",
    "quickcheck": "QuickCheck",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


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


def bootstrap_median_ci(values: np.ndarray, repetitions: int = 10000) -> tuple[float, float]:
    if len(values) == 0:
        return float("nan"), float("nan")
    if np.all(values == values[0]):
        value = float(values[0])
        return value, value
    rng = np.random.default_rng(SEED + len(values))
    samples = rng.choice(values, size=(repetitions, len(values)), replace=True)
    medians = np.median(samples, axis=1)
    low, high = np.percentile(medians, [2.5, 97.5])
    return float(low), float(high)


def paired_test(differences: list[float]) -> dict[str, float | int]:
    values = np.asarray(differences, dtype=float)
    eps = 1e-12
    nonzero = values[np.abs(values) > eps]
    wins = int(np.sum(values > eps))
    ties = int(np.sum(np.abs(values) <= eps))
    losses = int(np.sum(values < -eps))
    if len(nonzero) == 0:
        p_value = 1.0
        effect = 0.0
    else:
        p_value = float(
            wilcoxon(
                nonzero,
                alternative="two-sided",
                zero_method="wilcox",
                method="auto",
            ).pvalue
        )
        ranks = rankdata(np.abs(nonzero))
        positive = float(ranks[nonzero > 0].sum())
        negative = float(ranks[nonzero < 0].sum())
        effect = (positive - negative) / float(ranks.sum())
    low, high = bootstrap_median_ci(values)
    return {
        "pairs": len(values),
        "wins": wins,
        "ties": ties,
        "losses": losses,
        "mean_oriented_difference": float(values.mean()),
        "median_oriented_difference": float(np.median(values)),
        "median_ci_low": low,
        "median_ci_high": high,
        "rank_biserial": effect,
        "p_value": p_value,
    }


def holm_adjust(rows: list[dict]) -> None:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row["family"]].append(row)
    for family_rows in grouped.values():
        ordered = sorted(family_rows, key=lambda row: float(row["p_value"]))
        count = len(ordered)
        running = 0.0
        for index, row in enumerate(ordered):
            adjusted = min(1.0, (count - index) * float(row["p_value"]))
            running = max(running, adjusted)
            row["p_holm"] = running
            row["significant_0_05"] = running < 0.05


def generation_effects() -> list[dict]:
    rows = read_csv(RAW / "generation_runs.csv")
    index = {
        (
            row["method"],
            row["domain"],
            int(row["budget"]),
            int(row["repetition"]),
        ): row
        for row in rows
    }
    metrics = [
        ("coverage", "unique_rate", True),
        ("bug_discovery", "uniform_bugs", True),
        ("bug_discovery", "rare_branch_bugs", True),
        ("bug_discovery", "boundary_bugs", True),
        ("bug_discovery", "clustered_bugs", True),
        ("bug_discovery", "interaction_bugs", True),
        ("first_bug", "uniform_first", False),
        ("first_bug", "rare_branch_first", False),
        ("first_bug", "boundary_first", False),
        ("first_bug", "clustered_first", False),
        ("first_bug", "interaction_first", False),
        ("throughput_exploratory", "source_objects_per_s", True),
    ]
    keys = sorted(
        {
            (row["domain"], int(row["budget"]), int(row["repetition"]))
            for row in rows
            if row["method"] == "pdrs"
        }
    )
    output = []
    for comparator in COMPARATORS:
        for family, metric, higher_is_better in metrics:
            differences = []
            for domain, budget, repetition in keys:
                pdrs = float(index[("pdrs", domain, budget, repetition)][metric])
                other = float(index[(comparator, domain, budget, repetition)][metric])
                differences.append(
                    pdrs - other if higher_is_better else other - pdrs
                )
            output.append(
                {
                    "family": family,
                    "metric": metric,
                    "comparator": comparator,
                    "orientation": "positive_means_pdrs_better",
                    **paired_test(differences),
                }
            )
    return output


def aggregate_effects() -> list[dict]:
    output = []
    sources = [
        (
            "uniformity",
            RAW / "uniformity.csv",
            ("domain", "budget"),
            [
                ("object_total_variation", False),
                ("branch_total_variation", False),
            ],
        ),
        (
            "parallel_overlap",
            RAW / "worker_overlap.csv",
            ("domain",),
            [("overlap_fraction", False)],
        ),
        (
            "exact_throughput_exploratory",
            RAW / "exact_enumeration.csv",
            ("domain",),
            [("objects_per_s", True)],
        ),
    ]
    for family, path, key_fields, metrics in sources:
        rows = read_csv(path)
        index = {
            (row["method"],) + tuple(row[field] for field in key_fields): row
            for row in rows
        }
        pdrs_keys = sorted(
            tuple(row[field] for field in key_fields)
            for row in rows
            if row["method"] == "pdrs"
        )
        available = {row["method"] for row in rows}
        for comparator in COMPARATORS:
            if comparator not in available:
                continue
            comparator_keys = {
                tuple(row[field] for field in key_fields)
                for row in rows
                if row["method"] == comparator
            }
            shared = [key for key in pdrs_keys if key in comparator_keys]
            for metric, higher_is_better in metrics:
                differences = []
                for key in shared:
                    pdrs = float(index[("pdrs",) + key][metric])
                    other = float(index[(comparator,) + key][metric])
                    differences.append(
                        pdrs - other if higher_is_better else other - pdrs
                    )
                output.append(
                    {
                        "family": family,
                        "metric": metric,
                        "comparator": comparator,
                        "orientation": "positive_means_pdrs_better",
                        **paired_test(differences),
                    }
                )
    return output


def figures(rows: list[dict]) -> None:
    primary_metrics = [
        "unique_rate",
        "uniform_bugs",
        "rare_branch_bugs",
        "boundary_bugs",
        "branch_total_variation",
        "overlap_fraction",
    ]
    effect_lookup = {
        (row["metric"], row["comparator"]): float(row["rank_biserial"])
        for row in rows
    }
    matrix = np.asarray(
        [
            [effect_lookup.get((metric, comparator), np.nan) for comparator in COMPARATORS]
            for metric in primary_metrics
        ]
    )
    plt.figure(figsize=(10, 6))
    image = plt.imshow(matrix, vmin=-1, vmax=1, aspect="auto")
    plt.colorbar(image, label="Paired rank-biserial effect, positive favors PDRS")
    plt.xticks(np.arange(len(COMPARATORS)), [DISPLAY[value] for value in COMPARATORS], rotation=20)
    plt.yticks(np.arange(len(primary_metrics)), primary_metrics)
    plt.title("PDRS paired effects against five established systems")
    plt.tight_layout()
    plt.savefig(FIGURES / "paired_effect_heatmap.svg")
    plt.savefig(FIGURES / "paired_effect_heatmap.png", dpi=180)
    plt.close()

    generation = [
        row
        for row in rows
        if row["family"] in {"coverage", "bug_discovery", "first_bug"}
    ]
    wins = []
    ties = []
    losses = []
    for comparator in COMPARATORS:
        subset = [row for row in generation if row["comparator"] == comparator]
        wins.append(sum(int(row["wins"]) for row in subset))
        ties.append(sum(int(row["ties"]) for row in subset))
        losses.append(sum(int(row["losses"]) for row in subset))
    x = np.arange(len(COMPARATORS))
    plt.figure(figsize=(10, 5))
    plt.bar(x, wins, label="PDRS wins")
    plt.bar(x, ties, bottom=wins, label="Ties")
    bottoms = np.asarray(wins) + np.asarray(ties)
    plt.bar(x, losses, bottom=bottoms, label="PDRS losses")
    plt.xticks(x, [DISPLAY[value] for value in COMPARATORS], rotation=20)
    plt.ylabel("Paired observations across primary metrics")
    plt.title("PDRS win, tie, and loss counts")
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIGURES / "paired_win_tie_loss.svg")
    plt.savefig(FIGURES / "paired_win_tie_loss.png", dpi=180)
    plt.close()


def main() -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    rows = generation_effects() + aggregate_effects()
    holm_adjust(rows)
    write_csv(PROCESSED / "paired_effects.csv", rows)
    write_csv(
        PROCESSED / "win_tie_loss.csv",
        [
            {
                "family": row["family"],
                "metric": row["metric"],
                "comparator": row["comparator"],
                "pairs": row["pairs"],
                "wins": row["wins"],
                "ties": row["ties"],
                "losses": row["losses"],
            }
            for row in rows
        ],
    )
    significant_better = [
        row
        for row in rows
        if bool(row["significant_0_05"])
        and float(row["median_oriented_difference"]) > 0
    ]
    significant_worse = [
        row
        for row in rows
        if bool(row["significant_0_05"])
        and float(row["median_oriented_difference"]) < 0
    ]
    summary = {
        "tests": len(rows),
        "holm_families": sorted({row["family"] for row in rows}),
        "significant_pdrs_better": len(significant_better),
        "significant_pdrs_worse": len(significant_worse),
        "comparators": list(COMPARATORS),
        "note": "Positive oriented differences and positive rank-biserial effects favor PDRS. Throughput families are exploratory because method cells may run on different hosted runners.",
    }
    (PROCESSED / "publication_statistics.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )
    figures(rows)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
