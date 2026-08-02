from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import platform
import sys
import time
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from .common import FIGURES, PROCESSED, RAW, ROOT, ensure_dirs, write_checksums, write_json
from .eval_iso20022 import run as run_iso20022
from .eval_quantlib import run as run_quantlib
from .eval_simplefix import run as run_simplefix


def _plot_generation() -> None:
    frames = []
    for path in [RAW / "simplefix_methods.csv", RAW / "quantlib_generation.csv", RAW / "iso20022_generation.csv"]:
        frame = pd.read_csv(path)
        frames.append(frame[["evaluation", "method", "unique_rate", "generation_per_second"]])
    data = pd.concat(frames, ignore_index=True)
    labels = [f"{row.evaluation}\n{row.method.replace('_', ' ')}" for row in data.itertuples()]
    plt.figure(figsize=(14, 6))
    plt.bar(range(len(data)), data["unique_rate"] * 100.0)
    plt.xticks(range(len(data)), labels, rotation=45, ha="right")
    plt.ylabel("Unique generated objects, percent")
    plt.title("Duplicate-free generation across real-program domains")
    plt.ylim(0, 105)
    plt.tight_layout()
    plt.savefig(FIGURES / "real_program_unique_rate.svg", bbox_inches="tight")
    plt.savefig(FIGURES / "real_program_unique_rate.png", dpi=180, bbox_inches="tight")
    plt.close()


def _plot_simplefix() -> None:
    data = pd.read_csv(RAW / "simplefix_methods.csv")
    plt.figure(figsize=(9, 5))
    plt.bar(data["method"], data["coverage_percent"])
    plt.xticks(rotation=25, ha="right")
    plt.ylabel("SimpleFIX branch and line coverage, percent")
    plt.title("SimpleFIX coverage under matched generation budgets")
    plt.tight_layout()
    plt.savefig(FIGURES / "simplefix_coverage.svg", bbox_inches="tight")
    plt.savefig(FIGURES / "simplefix_coverage.png", dpi=180, bbox_inches="tight")
    plt.close()

    mutations = pd.read_csv(RAW / "simplefix_mutations.csv")
    table = mutations.groupby(["mutation", "outcome"]).size().unstack(fill_value=0)
    table.plot(kind="bar", stacked=True, figsize=(10, 5))
    plt.xticks(rotation=25, ha="right")
    plt.ylabel("Cases")
    plt.title("SimpleFIX behavior on controlled malformed messages")
    plt.tight_layout()
    plt.savefig(FIGURES / "simplefix_mutations.svg", bbox_inches="tight")
    plt.savefig(FIGURES / "simplefix_mutations.png", dpi=180, bbox_inches="tight")
    plt.close()


def _plot_quantlib() -> None:
    data = pd.read_csv(RAW / "quantlib_oracles.csv")
    errors = data[["analytic_error", "parity_error", "binomial_error", "finite_difference_error"]].copy()
    summary = []
    for column in errors:
        values = errors[column].dropna()
        summary.append({"oracle": column, "median": values.median(), "p95": values.quantile(0.95), "max": values.max()})
    frame = pd.DataFrame(summary)
    plt.figure(figsize=(9, 5))
    plt.bar(frame["oracle"], frame["p95"].clip(lower=1e-16))
    plt.yscale("log")
    plt.xticks(rotation=25, ha="right")
    plt.ylabel("95th percentile absolute error, log scale")
    plt.title("QuantLib differential-oracle error")
    plt.tight_layout()
    plt.savefig(FIGURES / "quantlib_oracle_error.svg", bbox_inches="tight")
    plt.savefig(FIGURES / "quantlib_oracle_error.png", dpi=180, bbox_inches="tight")
    plt.close()


def _plot_iso20022() -> None:
    data = pd.read_csv(RAW / "iso20022_validation.csv")
    latency = data.groupby("message")["validation_ms"].median().reset_index()
    plt.figure(figsize=(8, 5))
    plt.bar(latency["message"], latency["validation_ms"])
    plt.ylabel("Median two-validator latency, ms")
    plt.title("Official ISO 20022 XSD validation latency")
    plt.tight_layout()
    plt.savefig(FIGURES / "iso20022_validation_latency.svg", bbox_inches="tight")
    plt.savefig(FIGURES / "iso20022_validation_latency.png", dpi=180, bbox_inches="tight")
    plt.close()

    mutations = pd.read_csv(RAW / "iso20022_mutations.csv")
    rejected = mutations.assign(rejected=(~mutations["lxml_valid"] & ~mutations["xmlschema_valid"]))
    rates = rejected.groupby("mutation")["rejected"].mean().reset_index()
    plt.figure(figsize=(9, 5))
    plt.bar(rates["mutation"], rates["rejected"] * 100.0)
    plt.xticks(rotation=25, ha="right")
    plt.ylabel("Rejected by both validators, percent")
    plt.title("ISO 20022 controlled-invalid rejection")
    plt.ylim(0, 105)
    plt.tight_layout()
    plt.savefig(FIGURES / "iso20022_mutation_rejection.svg", bbox_inches="tight")
    plt.savefig(FIGURES / "iso20022_mutation_rejection.png", dpi=180, bbox_inches="tight")
    plt.close()


def _environment() -> dict[str, Any]:
    import QuantLib as ql
    import simplefix
    import xmlschema
    from lxml import etree

    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "packages": {
            "QuantLib": getattr(ql, "__version__", "unknown"),
            "simplefix": getattr(simplefix, "__version__", "1.0.17"),
            "xmlschema": xmlschema.__version__,
            "lxml": ".".join(str(item) for item in etree.LXML_VERSION),
        },
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def _verify(summary: dict[str, Any]) -> None:
    failures: list[str] = []
    if summary["simplefix"]["valid_oracle_failures"] != 0:
        failures.append(f"SimpleFIX valid-message failures: {summary['simplefix']['valid_oracle_failures']}")
    if summary["quantlib"]["oracle_failures"] != 0:
        failures.append(f"QuantLib oracle failures: {summary['quantlib']['oracle_failures']}")
    if summary["iso20022"]["valid_document_failures"] != 0:
        failures.append(f"ISO 20022 valid-document failures: {summary['iso20022']['valid_document_failures']}")
    if summary["iso20022"]["mutation_rejection_rate"] < 0.99:
        failures.append(f"ISO 20022 mutation rejection below 99%: {summary['iso20022']['mutation_rejection_rate']}")
    for evaluation in ["simplefix", "quantlib", "iso20022"]:
        if summary[evaluation]["pdrs_overlap_fraction"] != 0.0:
            failures.append(f"{evaluation} PDRS worker overlap was nonzero")
    if failures:
        raise SystemExit("Real-program evidence verification failed:\n- " + "\n- ".join(failures))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--xsd-dir", type=Path, required=True)
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()
    ensure_dirs()
    budgets = {"simplefix": 800 if args.quick else 3000, "quantlib": 300 if args.quick else 1200, "iso20022": 200 if args.quick else 800}
    summary = {
        "simplefix": run_simplefix(budget=budgets["simplefix"]),
        "quantlib": run_quantlib(budget=budgets["quantlib"]),
        "iso20022": run_iso20022(args.xsd_dir, budget=budgets["iso20022"]),
        "environment": _environment(),
    }
    _plot_generation()
    _plot_simplefix()
    _plot_quantlib()
    _plot_iso20022()
    write_json(PROCESSED / "real_program_summary.json", summary)
    write_json(PROCESSED / "environment.json", summary["environment"])
    write_checksums()
    _verify(summary)
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
