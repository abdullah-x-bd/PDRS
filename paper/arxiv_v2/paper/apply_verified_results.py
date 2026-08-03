from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
source = HERE / "main.tex"
target = HERE / "main_verified.tex"
text = source.read_text(encoding="utf-8")

replacements = {
    "3,421 exhaustively enumerated objects": "3,428 exhaustively enumerated objects",
    (
        "Across the 96 paired bootstrap comparisons, most intervals include zero; "
        "several comparisons support PDRS and more support a targeted comparator. "
        "The result directly narrows the claim: PDRS supplies exact object addressing "
        "and a useful default distribution, while defect-sensitive workflows should "
        "choose or learn an appropriate sampling objective."
    ): (
        "Across the 96 paired bootstrap comparisons, one interval supports PDRS, "
        "13 support a targeted comparator, and 82 include zero. PDRS outperforms "
        "boundary-biased sampling for pairwise-interaction defects at budget 1,000. "
        "Boundary-biased or branch-balanced sampling leads in the supported boundary, "
        "rare-branch, branch-uniform, and historical-like comparisons. The result "
        "directly narrows the claim: PDRS supplies exact object addressing and a useful "
        "default distribution, while defect-sensitive workflows should choose or learn "
        "an appropriate sampling objective."
    ),
    (
        "The workflow archives exact versions and raw JSON. A result enters the paper "
        "as a software defect only after independent upstream confirmation. Otherwise "
        "it remains a conformance, boundary, or parser-behavior observation."
    ): (
        "The verified extension completed all three target jobs. QuantLib 1.43 completed "
        "10 of 12 declared boundary cases. Its CRR binomial engine raised "
        "\\texttt{RuntimeError: negative probability} for both call and put cases at "
        "volatility $10^{-6}$; the analytic and independent-formula checks were not "
        "reported as failures. We record this as a reproducible numerical-engine "
        "boundary observation, not a confirmed library defect. SimpleFIX 1.0.17 parsed "
        "all four valid profiles. Across 24 malformed-message probes, it returned a "
        "message in 16 cases, returned no message in four, and raised an exception in "
        "four; these outcomes characterize parser behavior rather than session-level "
        "FIX conformance. Both ISO validators accepted the two valid profiles, agreed "
        "on every mutation outcome, and jointly rejected 10 of 12 probes. Both accepted "
        "the $1.001$ amount probe, showing that this precision was permitted by the "
        "evaluated schema facets and should not be classified as invalid.\n\n"
        "The workflow archives exact versions and raw JSON. A result enters the paper "
        "as a software defect only after independent upstream confirmation. Otherwise "
        "it remains a conformance, boundary, or parser-behavior observation."
    ),
}

for old, new in replacements.items():
    if old not in text:
        raise SystemExit(f"expected manuscript passage is missing: {old[:80]!r}")
    text = text.replace(old, new, 1)

for forbidden in (
    "3,421 exhaustively enumerated objects",
    "several comparisons support PDRS",
):
    if forbidden in text:
        raise SystemExit(f"stale provisional language remains: {forbidden}")

target.write_text(text, encoding="utf-8")
print(target)
