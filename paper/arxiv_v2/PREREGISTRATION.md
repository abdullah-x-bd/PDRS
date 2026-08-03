# Preregistered revision protocol

This document fixes the redesigned analysis before the branch is merged.

## RQ1 Semantic correctness

Test exact count, rank, unrank, typed lowering, malformed-schema rejection, Unicode canonicalization, and cross-policy partition completeness. The independent oracle recursively enumerates the schema without using PDRS counts or rank arithmetic.

## RQ2 Compilation and access scalability

Vary path depth, top-level branch count, and graph sharing. Record compiler latency, compiled node count, cardinality bit length, and rank/unrank latency. Compare the graph representation with an exact reduced multivalued decision diagram implemented in the artifact. The MDD is a representative knowledge-compilation baseline and is not presented as KUS or d-DNNF.

## RQ3 Sampling and defect objectives

Methods: no-replacement object-uniform ranks, replacement ranks, branch-balanced ranks, boundary-biased ranks, and a simple coverage-guided rank selector.

Defect distributions: object-uniform, branch-uniform, rare-branch, boundary, pairwise interaction, clustered local, execution-derived, and historical-like edge cases.

Budgets: 100, 500, and 1,000. Repetitions: 30. Report attempts, distinct objects, duplicates, distinct defects, first-defect position, execution-cost units, and defects per 1,000 cost units.

## RQ4 Distributed orchestration

Compare contiguous, strided, hash, affine-permuted, and centrally shuffled assignments across eight workers. Measure overlap, object-count variation, heterogeneous execution-cost variation, maximum worker cost, branch-distribution variation, coordination units, replayability, and remaining ranks after a simulated worker failure.

## RQ5 Statistical analysis

A complete seeded campaign is the independent unit. Pair methods within repetition, budget, and defect distribution. Bootstrap complete paired campaigns 2,000 times and report the median paired difference with a 95 percent percentile interval. P-values remain secondary and are omitted from the synthetic revision where the paired intervals answer the declared question directly.

## RQ6 Real programs

Run the existing finance stack in a separate CI job. Extend QuantLib with boundary regimes and differential checks, SimpleFIX with four message families and six malformed-message transformations, and ISO 20022 with facet, ordering, cardinality, and enumeration mutations. Record behavior without calling a result a defect unless an independent upstream review confirms it.

## Stopping rules

Synthetic experiments use the fixed design above. External jobs stop when every declared case executes or the workflow records a reproducible dependency or target failure. Failed external cells remain evidence and are not converted into PDRS wins.
