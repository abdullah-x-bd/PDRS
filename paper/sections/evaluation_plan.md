# Evaluation plan

## RQ1: Correctness

Does the compiler implement a bijection for every supported schema?

Evidence: proof, exhaustive small-domain tests, generated-schema tests, malformed-schema challenge set.

## RQ2: Density

How close does whole-domain ranking approach `ceil(log2 N)` and when does it outperform field-oriented allocations?

Evidence: synthetic sparsity sweep and real schema corpus; later comparisons with ASN.1 PER and Protocol Buffers.

## RQ3: Performance

Measure compile time, rank and unrank throughput, p50/p95/p99 latency, memory, and scaling with nodes, edges, depth, and domain bits.

## RQ4: Fuzzing

Compare uniform rank sampling, rejection sampling, grammar generation, and mutation fuzzing on validity, unique coverage, rare branches, duplicates, and failure reproducibility.

## RQ5: Evolution

Quantify rank churn after edits at different depths and compare versioning, reserved intervals, and indirection strategies.

## RQ6: Cryptographic adaptation

Evaluate only through an established permutation or FPE primitive. Measure domain safety, format validity, performance, version binding, integrity composition, and side channels.

## Statistical discipline

- register hypotheses and metrics before full runs
- retain negative results
- publish raw and processed data
- use fixed random seeds where appropriate
- separate deterministic and hardware-dependent results
- report uncertainty and effect sizes, not only point estimates
