# Path-Dependent Radix Spaces (PDRS)

PDRS is a research prototype for representing finite constrained objects as paths through a state-dependent radix space. A schema describes which choices are valid at each state. The compiler computes the exact domain size and provides a canonical bijection between valid objects and the integer interval `0..N-1`.

The repository is both software and a reproducible research workspace. Every paper claim is linked to mathematical definitions, tests, experiments, prior art, and red-team findings.

## Current scope

The reference implementation supports finite acyclic schemas composed of:

- `choice` nodes with ordered labelled branches
- inclusive bounded integer `range` nodes
- `terminal` nodes

It provides:

- exact domain counting
- schema validation and cycle detection
- canonical `rank` and `unrank`
- uniform sampling by rank
- canonical schema hashing
- a command-line interface
- exhaustive and randomized correctness tests
- deterministic density benchmarks

This is intentionally narrower than the full research programme. Arbitrary predicates, recursive schemas, stable identifiers under schema mutation, authenticated format-preserving encryption, and formally verified code generation are tracked as open work rather than claimed as solved.

## Core idea

For a state `q`, let `A(q)` be its ordered valid choices and let `C(q)` be the number of complete objects reachable from it. For a terminal state, `C(q)=1`. Otherwise:

```math
C(q)=\sum_{a\in A(q)} C(\delta(q,a)).
```

The rank contribution of a selected branch is the sum of the sizes of all earlier sibling subtrees. This generalizes fixed mixed-radix arithmetic to path-dependent domains in which later choices depend on earlier choices.

## Quick start

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m pdrs.cli count schemas/permit.json
PYTHONPATH=src python -m pdrs.cli rank schemas/permit.json '["experimental", 7, 13]'
PYTHONPATH=src python -m pdrs.cli unrank schemas/permit.json 3493
python scripts/run_benchmarks.py --output results/baseline_density.csv
python scripts/check_research_assets.py
```

Expected permit results:

```text
count = 4000
rank(["experimental", 7, 13]) = 3493
unrank(3493) = ["experimental", 7, 13]
```

## Research questions

1. Which finite dependent schemas admit efficient exact counting, ranking, and unranking?
2. How close can generated encodings approach the information-theoretic lower bound?
3. When does whole-domain ranking improve valid-input fuzzing and reproducibility?
4. How severe is rank churn under schema evolution, and what versioning mechanisms are necessary?
5. Can a schema compiler safely generate adapters for established small-domain or format-preserving cryptography?
6. Which native operations over path-dependent representations are finite-state computable?

## Repository map

- `src/pdrs/` reference compiler and CLI
- `tests/` correctness and adversarial tests
- `schemas/` versioned benchmark schemas
- `theory/` definitions, theorem statements, and limitations
- `literature/` source registry, prior-art matrix, and claim-evidence ledger
- `experiments/` preregistered experiment manifests
- `results/` deterministic generated results
- `red_team/` assumptions, attacks, and counterexamples
- `paper/` manuscript skeleton and evaluation plan
- `.github/` CI, reproducibility workflows, and research issue forms

## Status

Research prototype, version `0.1.0`. No cryptographic deployment is claimed or recommended. The encryption direction is a future adapter around established cryptographic primitives, not a claim that hidden radices provide security.

## Citation

Citation metadata is available in `CITATION.cff`.
