# Phases 1–9 implementation record

## Phase 1. Frozen artifact

Completed in source:

- exact PDRS and FinSpace commit SHAs
- separate published-package and repository-evidence labels
- pinned Python analysis requirements
- Dockerfile
- one-command synthetic reproduction
- SHA-256 generation
- separate external-program evidence directory

External owner action still required: connect the repository to Zenodo and create an immutable GitHub release. No DOI is invented.

## Phase 2. Prior work and positioning

Completed in manuscript and capability matrix:

- SciFe
- Feat
- enumerative coding
- knowledge compilation and KUS
- Korat
- TestEra
- Luck
- QuickCheck
- SmallCheck
- Grammarinator
- Hypothesis
- ACTS

The paper claims systems novelty and empirical contribution. It explicitly assigns counting, ranking, unranking, and uniform index sampling to established foundations.

## Phase 3. Formal model

Completed:

- typed canonical value model
- NFC string normalization
- precise graph well-formedness
- path-wise field uniqueness
- token-level bijection
- injective-lowering theorem
- bit-complexity variables
- Floyd sampling without replacement
- native 64-bit versus Python arbitrary-precision boundary
- object replay versus execution replay

## Phase 4. Baselines

Completed:

- retained native Feat comparison from frozen evidence
- added SciFe as closest prior work and direct capability comparison
- added exact reduced MDD baseline for the knowledge-compilation family
- separated testing objectives instead of combining all systems into one score

Remaining venue-strength extension: run a native SciFe implementation and an external d-DNNF/KUS compiler on the complete benchmark corpus.

## Phase 5. Defect study

Completed:

- eight defect distributions
- five generation policies
- equal-attempt and cost-normalized metrics
- 30 paired campaigns
- three budgets
- distinct defects and first-defect position
- no universal bug-finding claim

## Phase 6. Distributed orchestration

Completed:

- contiguous intervals
- strided ranks
- hash allocation
- affine-permuted intervals
- central global shuffle
- heterogeneous execution costs
- overlap
- object-count balance
- cost balance
- branch balance
- coordination state
- failure recovery
- replayability

## Phase 7. Pareto correction

Completed. The manuscript removes the Pareto-frontier claim and the 24/26/27 win-loss headline. It reports objective-specific results and uncertainty.

## Phase 8. Statistical analysis

Completed:

- complete seeded campaign as independent unit
- paired campaign differences
- budget prefixes treated as nested
- 2,000-replicate paired bootstrap
- confidence intervals and practical direction
- raw observation table generated from code

## Phase 9. Real-program expansion

Implemented and executed by GitHub Actions:

- QuantLib boundary regimes and differential checks
- SimpleFIX four-family parser behavior and six mutations
- ISO 20022 facet, ordering, date, unexpected-element, and enumeration mutations
- separate v2 output directory
- no automatic defect classification
- exact target-package and XSD evidence archived

The final manuscript can incorporate only results from the successful workflow artifact. A previously unknown defect requires independent upstream confirmation.
