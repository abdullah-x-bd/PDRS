# Five-baseline comparison protocol

This campaign compares PDRS with five established structured-generation systems using their native public APIs.

## Scored systems

1. **Feat 1.1.1.1** — exact functional enumeration and integer indexing of algebraic data types.
2. **SmallCheck 1.2.1.1** — exhaustive depth-bounded enumeration.
3. **Hypothesis 6.160.0** — mature property-based generation with shrinking-oriented search.
4. **Grammarinator 26.1** — ANTLR-based grammar generation, using its duplicate memoization mode.
5. **QuickCheck 2.18.0.0** — foundational property-based random generation, using native Haskell generators with shrinking disabled during measurement.

PDRS is evaluated as the focal sixth system.

## Attempted unscored system

**CombOL 0.1.11** was also implemented through its native finite sum/product sampler. Across multiple independent matched-domain jobs, the CombOL/Symbolica process repeatedly caused the GitHub-hosted runner to receive an external shutdown signal before a result chunk was produced. This is retained as operational evidence, but it is not converted into a quality or performance score and is not counted as a PDRS win.

## Matched domains

Five finite domains are represented without rejection-only semantic predicates:

| Domain | Valid objects | Structure |
|---|---:|---|
| Balanced product | 2,048 | Three independent bounded fields |
| Imbalanced choice | 2,322 | Four alternatives ranging from 2 to 2,048 objects |
| Dependent record | 6,288 | Four alternatives with different field counts and radices |
| Protocol message | 1,112 | Type-dependent control-message fields |
| Action space | 2,496 | Action-dependent parameter spaces |

Every domain contains more than 1,000 valid objects. Therefore the 100, 500, and 1,000-case conditions are distinct in every domain.

Every generated object is converted to a shared canonical integer identifier. All validity, uniqueness, coverage, bug, and overlap statistics are calculated outside the compared tools.

## Fairness rules

- Feat receives exact global indexing and no-replacement selection.
- SmallCheck receives its native exhaustive order rather than being converted into a random generator.
- Hypothesis uses declarative `one_of` and integer strategies with generation enabled and shrinking disabled during measurement.
- Grammarinator uses a generated ANTLR grammar plus its public memoization facility to reduce duplicates.
- QuickCheck uses native `Gen` combinators with locally uniform constructor selection and bounded-field generators. Shrinking is not invoked during generation measurement, but shrinking remains recorded as a supported capability.
- PDRS uses rank sampling without replacement.
- Exact-enumeration metrics are reported only for methods exposing that capability.
- Unsupported capabilities are recorded in the capability matrix rather than converted into artificial zero scores.
- Steady-state generation time excludes language and package installation. Generator/schema preparation is separated from campaign-quality measurements.
- Runtime comparisons are exploratory because separate method-domain cells may execute on different hosted runners. Generation quality, coverage, uniformity, duplicate rates, bug reach and overlap are the primary comparisons.

## Workloads

- Budgets: 100, 500, and 1,000.
- Repetitions: 20.
- Scored methods: 6, comprising PDRS and five comparators.
- Domains: 5.
- Reported matched rows: 1,800.
- Each method-domain job performs 20 maximum-budget campaigns. The 100 and 500-case measurements are exact prefixes of the same campaign used for the 1,000-case result. This preserves paired comparison while avoiding redundant tool initialization.
- Bug distributions:
  - uniformly placed
  - rare-branch
  - field and branch boundaries
  - clustered interval
  - cross-field interaction
- Four-worker overlap is measured using coordinated partitions where a method supports them and independent seeded campaigns otherwise.

## Statistical analysis

PDRS is paired with each comparator on the same domain, budget and repetition. The accepted evidence includes:

- two-sided Wilcoxon signed-rank tests
- Holm correction within metric families
- matched rank-biserial effect sizes
- bootstrap 95 percent intervals for median paired differences
- win, tie and loss counts
- explicit orientation where positive values favor PDRS

Uniformity and worker-overlap metrics use their natural matched domain and budget units. Throughput tests are marked exploratory because runner allocation is not hardware-identical across every matrix cell.

## Execution isolation

The workflow runs a 30-cell matrix containing every scored method-domain combination. A failed or slow external system cannot invalidate completed chunks from other systems. The aggregate stage requires all 30 scored chunks before producing any accepted evidence.

## Outputs

- `results/sota/raw/exact_enumeration.csv`
- `results/sota/raw/generation_runs.csv`
- `results/sota/raw/uniformity.csv`
- `results/sota/raw/worker_overlap.csv`
- `results/sota/processed/summary.json`
- `results/sota/processed/capabilities.csv`
- `results/sota/processed/attempted_baselines.csv`
- `results/sota/processed/chunk_audit.csv`
- `results/sota/processed/paired_effects.csv`
- `results/sota/processed/win_tie_loss.csv`
- `results/sota/processed/publication_statistics.json`
- generated SVG and PNG figures
- package and runtime metadata
- SHA-256 manifest
