# Five-baseline comparison protocol

This campaign compares PDRS with five established structured-generation systems using their native public APIs.

## Systems

1. **Feat 1.1.1.1** — exact functional enumeration and integer indexing of algebraic data types.
2. **SmallCheck 1.2.1.1** — exhaustive depth-bounded enumeration.
3. **Hypothesis 6.160.0** — mature property-based generation with shrinking-oriented search.
4. **Grammarinator 26.1** — ANTLR-based grammar generation, using its duplicate memoization mode.
5. **CombOL 0.1.11** — Boltzmann sampling of explicitly specified combinatorial classes.

PDRS is evaluated as the focal sixth system.

## Matched domains

Five finite domains are represented without rejection-only semantic predicates:

- balanced three-field product
- strongly imbalanced tagged choice
- dependent record
- protocol message
- state-dependent action space

Every generated object is converted to a shared canonical integer identifier. All validity, uniqueness, coverage, bug, and overlap statistics are therefore calculated outside the compared tools.

## Fairness rules

- Feat receives exact global indexing and no-replacement selection.
- SmallCheck receives its native exhaustive order rather than being converted into a random generator.
- Hypothesis uses declarative `one_of` and integer strategies with generation enabled and shrinking disabled during measurement.
- Grammarinator uses a generated ANTLR grammar plus its public memoization facility to reduce duplicates.
- CombOL uses a finite sum/product specification whose branches are padded to equal combinatorial size, making the target structures equiprobable under equal atom parameters.
- PDRS uses rank sampling without replacement.
- Compilation/setup costs are retained separately from campaign-quality metrics.
- Exact-enumeration metrics are reported only for methods exposing that capability.
- No unsupported capability is imputed as a failure score.

## Workloads

- Budgets: 100, 500, and 1,000, capped by domain cardinality.
- Repetitions: 20.
- Bug distributions:
  - uniformly placed
  - rare-branch
  - field and branch boundaries
  - clustered interval
  - cross-field interaction
- Four-worker overlap is measured using coordinated partitions where a method supports them and independent seeded runs otherwise.

## Outputs

- `results/sota/raw/exact_enumeration.csv`
- `results/sota/raw/generation_runs.csv`
- `results/sota/raw/uniformity.csv`
- `results/sota/raw/worker_overlap.csv`
- `results/sota/processed/summary.json`
- `results/sota/processed/capabilities.csv`
- generated SVG and PNG figures
- package and runtime metadata
- SHA-256 manifest
