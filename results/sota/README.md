# State-of-the-art structured-generation comparison

This directory contains the complete verified evidence for the matched comparison of PDRS against five established systems:

- Feat 1.1.1.1
- SmallCheck 1.2.1.1
- Hypothesis 6.160.0
- Grammarinator 26.1
- QuickCheck 2.18.0.0

CombOL 0.1.11 was attempted but not scored. Its native CombOL/Symbolica sampler repeatedly caused externally terminated GitHub-hosted runners before a complete comparison cell was produced. No quality or performance conclusion is inferred from that operational failure.

## Experimental design

- 5 matched finite structured domains
- 6 scored systems including PDRS
- 30 independently isolated method-domain cells
- budgets of 100, 500, and 1,000 objects
- 20 repetitions per condition
- 1,800 matched generation rows
- 15 exact-enumeration measurements
- 77 paired statistical comparisons
- Holm familywise correction
- rank-biserial effect sizes
- bootstrap confidence intervals
- five bug-location distributions
- four-worker overlap measurements

Every scored system emitted valid objects in the matched domains.

## Headline descriptive results

| Method | Median unique rate | Median branch TV | Median worker overlap | Exact domains complete |
|---|---:|---:|---:|---:|
| PDRS | 1.000 | 0.00305 | 0.000 | 5/5 |
| Feat | 1.000 | 0.00270 | 0.000 | 5/5 |
| SmallCheck | 1.000 | 0.26851 | 0.000 | 5/5 |
| Hypothesis | 1.000 | 0.15600 | 0.4525 | not supported |
| Grammarinator | 1.000 | 0.24991 | 0.3730 | not supported |
| QuickCheck | 0.668 | 0.57166 | 0.2932 | not supported |

Lower branch total variation and worker overlap are better.

PDRS and Feat occupy the same principal capability frontier in this corpus: exact complete enumeration, random access, object-uniform no-replacement generation, and coordinated zero-overlap partitioning. Feat was substantially faster in the current language-level pipeline measurement. PDRS contributes an external declarative schema compiler, canonical cross-language IR, and independently conforming Python, C, and Rust engines.

SmallCheck was especially effective for bugs deliberately placed near early enumeration boundaries and rare early branches, but its deterministic prefix order was strongly nonuniform over complete objects. Hypothesis and Grammarinator provide broader testing ecosystems and recursive-generation capabilities, but independent workers overlapped materially in the matched campaigns. QuickCheck generated quickly but repeated many objects and was highly biased by constructor-local generation on imbalanced domains.

Across the 77 paired tests, after Holm correction, PDRS was significantly better in 24 comparisons and significantly worse in 26. These counts are not an overall league table because the tests measure different and sometimes conflicting objectives. In particular, throughput comparisons are explicitly exploratory because method cells may execute on different hosted runners.

The defensible empirical conclusion is therefore not that PDRS dominates every existing method. It is that PDRS is a strong Pareto-front method for finite dependent domains when the required properties are exact object-uniformity, no repetition, random access, complete enumeration, deterministic reproduction, and provably disjoint distributed partitions.

## Evidence files

### Raw results

- `raw/generation_runs.csv`
- `raw/exact_enumeration.csv`
- `raw/uniformity.csv`
- `raw/worker_overlap.csv`
- `chunks/` contains every method-domain sequence and row bundle
- `haskell/` contains native Feat, SmallCheck, and QuickCheck outputs

### Processed evidence

- `processed/summary.json`
- `processed/paired_effects.csv`
- `processed/win_tie_loss.csv`
- `processed/publication_statistics.json`
- `processed/capabilities.csv`
- `processed/chunk_audit.csv`
- `processed/attempted_baselines.csv`
- `processed/environment.json`
- `processed/SHA256SUMS.csv`

### Figures

SVG and PNG versions are available for:

- unique output rate
- object-distribution accuracy
- worker overlap
- uniform, rare-branch, and boundary bug discovery
- exact enumeration throughput
- paired effect heatmap
- win-tie-loss summary

## Interpretation limits

- These are controlled finite-domain experiments, not real-program vulnerability discoveries.
- Bug locations are synthetic and intentionally cover several distributions.
- Throughput across separately scheduled GitHub runners is exploratory.
- Feat is the closest comparator and matches several core PDRS guarantees.
- SmallCheck, Hypothesis, Grammarinator, and QuickCheck optimize different objectives and should not be described as universally inferior.
- The experiment supports a differentiated capability claim, not universal state-of-the-art dominance.
