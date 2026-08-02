# Experiment registry

All full-scale outputs are committed under `results/`. Every stage uses seed `20260802` unless a row-specific deterministic seed is documented.

| ID | Stage | Main question | Scale | Primary outputs |
|---|---|---|---:|---|
| E001 | Correctness | Are count, rank, unrank and ordering exact? | 7 static + 1,000 generated schemas | `correctness.csv`, `theorem_verification.json` |
| E002 | Density | How close is PDRS to the domain lower bound? | 7 static + 11 imbalance points | `density_static.csv`, `density_imbalance.csv` |
| E003 | Runtime | How do compile, rank and unrank scale? | 7 static + 17 scaling points | `runtime_static.csv`, `runtime_scaling.csv` |
| E004 | Uniformity | Does the implementation realize uniform rank sampling? | 750,000 samples | `uniformity*.csv` |
| E005 | Fuzzing | How do validity, uniqueness, overlap and bug discovery compare? | 560 runs | `fuzzing_runs.csv`, `fuzzing_parallel_overlap.csv` |
| E006 | Evolution | How much rank churn follows schema edits? | 6 mutations × 4,000 base objects | `schema_evolution.csv` |
| E007 | Faults | What happens under single-bit rank corruption? | 7 schemas × 1,500 ranks × bit width | `fault_propagation.csv` |
| E008 | Scalability and timing | Are resource controls effective and is timing branch-dependent? | 4 attacks + 256 branch positions | `resource_limits.csv`, `timing_branch_index.csv` |
| E009 | Domain permutation | Does rank-permute-unrank remain bijective and authenticated? | 4 domains | `crypto_permutation.csv`, `crypto_avalanche.csv` |

## Stopping and analysis rules

- Correctness and permutation experiments require zero failures.
- Static domains below the configured threshold are checked exhaustively.
- Large domains use deterministic samples recorded by seed.
- Fuzzing reports medians and empirical 2.5/97.5 percentiles over 40 repetitions.
- Uniformity uses exact bucket cardinalities, not an equal-bucket approximation.
- Runtime and timing results are reported with environment metadata and are not expected to be byte-identical across hardware.
- Negative results remain committed and appear in `red_team/RESULTS.md`.
