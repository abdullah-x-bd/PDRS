# PDRS v0.2 experimental evidence report

## Scope

This report covers proofs, implementation validation, experiments, data, graphs, and robustness findings. It does not draft the research paper or make a final novelty claim.

## Headline findings

1. **Correctness:** 254,609 objects were checked across seven static schemas and 1,000 generated schemas. No count, rank, unrank, ordering, or inverse failure occurred.
2. **Density:** PDRS achieved the information-theoretic fixed-width bound on every schema. The median saving was 1 bit per object against the UPER subset and 41 bits per object against the generic protobuf wire baseline.
3. **Performance:** Across the static corpus, median rank latency was 1.215 microseconds and median unrank latency was 1.293 microseconds in the recorded GitHub runner environment.
4. **Uniformity:** Five schemas received 150,000 samples each. The maximum total variation across 100 exact-cardinality rank buckets was 0.0106 and the minimum chi-square p-value was 0.178.
5. **Fuzzing:** At 3,500 attempts, PDRS produced exactly 3,500 unique valid objects in every repetition. Direct grammar produced a median 1,720, mutation 777.5, and naive rejection 334.5. PDRS found a median 22 of 64 seeded bugs, compared with 8 for direct grammar and 2 for mutation and naive rejection.
6. **Parallel work:** Exact rank partitioning had zero overlap. Four independent grammar workers had median overlap of 15.4 percent.
7. **Evolution:** Appending a branch preserved every existing rank. Inserting a branch first or reversing root order changed every existing rank. Expanding an early branch changed 97.5 percent.
8. **Faults:** A median 92.8 percent of raw dense-rank single-bit flips decoded to another valid object. Dense ranks therefore need an integrity layer. A checksum or MAC detects all single-bit alterations in the tested model.
9. **Resource controls:** All four configured resource-exhaustion attacks were rejected quickly.
10. **Timing:** The Python reference implementation is not constant time. Branch-index timing dependence was measurable in ranking on the recorded runner. No constant-time claim is made for either operation.
11. **Domain permutation:** No permutation or inverse failure occurred across four domains. Authentication rejected every tampered tag. Mean avalanche was 0.478, but the construction remains research-only.

## Correctness and proof evidence

The mathematical proof is in `theory/proofs.md`. It establishes finite positive cardinality, disjoint contiguous sibling intervals, rank bounds, both inverse identities, uniformity, exact worker partitioning, complexity, rank-instability counterexamples, and domain-permutation composition.

The independent executable model checker does not reuse the PDRS ranking algorithm. It naively enumerates each generated tree in canonical order and checks that count, rank, and unrank match that independent specification.

## Density results

PDRS is strongest when branch subdomains are highly imbalanced or when early choices change the remainder of the schema. It cannot improve on a field encoding that is already globally optimal. The two-year calendar is such a case: both PDRS and the local UPER subset use 10 bits.

The compiler AST receives the largest local-packing gain in the static corpus: 18 PDRS bits versus 21.84 average UPER-subset bits. The benefit comes from the very large call-expression subtree and much smaller literal and variable subtrees.

## Fuzzing interpretation

The strongest result is exact nonrepetition. PDRS can address the valid domain directly, select ranks without replacement, divide rank intervals among workers, and reproduce a failure from one rank. Direct grammar remains useful when branch-level rather than object-level balance is desired, but it is biased relative to the object domain and repeats heavily.

The bug experiment seeds bugs uniformly over the valid object domain. Therefore object-uniform PDRS sampling is aligned with the target distribution. Different bug distributions may favor a targeted or weighted grammar. This is a boundary, not a defect hidden from the results.

## Negative results

- PDRS fixed ranks save little or nothing against local field packing on balanced product domains.
- Whole-domain ranks are not stable identifiers under arbitrary schema edits.
- Raw dense ranks are poor error-detecting codes.
- The Python implementation leaks timing information and must not be called constant time.
- The cryptographic adapter proves invertibility and measures diffusion, but does not establish standard-grade cryptographic security.
- Uniform rank sampling is not automatically optimal for branch coverage or nonuniform real-world object distributions.

## Reproducibility

Raw data is in `results/raw`, derived tables in `results/processed`, figures in `results/figures`, and checksums in `results/processed/SHA256SUMS.csv`. Runtime metadata is recorded separately because performance results cannot be byte-identical across hardware.
