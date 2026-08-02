# PDRS v0.3 experimental evidence report

## Scope

This report covers proofs, implementation validation, experiments, data, graphs, robustness findings, and independent C and Rust conformance. It does not draft the research paper or make a final novelty claim.

## Headline findings

1. **Python correctness:** 254,609 objects were checked across seven static schemas and 1,000 generated schemas. No count, rank, unrank, ordering, or inverse failure occurred.
2. **Independent native correctness:** The C and Rust engines completed 389,754 exhaustive native round trips across the seven committed schemas with zero failures. They also matched Python on 22,096 deterministic cross-language vectors with zero mismatches.
3. **Native toolchain gates:** C passed strict `-Werror` compilation plus AddressSanitizer and UndefinedBehaviorSanitizer. Rust passed formatting, Clippy with every warning denied, and an optimized release build.
4. **Density:** PDRS achieved the information-theoretic fixed-width bound on every schema. The median saving was 1 bit per object against the UPER subset and 41 bits per object against the generic protobuf wire baseline.
5. **Python performance:** Across the static corpus, median rank latency was about 1.21 microseconds and median unrank latency was about 1.29 microseconds in the committed Python run.
6. **Native performance:** In the committed GitHub-runner dataset with 200,000 iterations per schema and language, median rank speedup relative to Python was 49.4x for C and 62.7x for Rust. Median unrank speedup was 136.5x for C and 38.8x for Rust.
7. **Uniformity:** Five schemas received 150,000 samples each. The maximum total variation across 100 exact-cardinality rank buckets was 0.0106 and the minimum chi-square p-value was 0.178.
8. **Fuzzing:** At 3,500 attempts, PDRS produced exactly 3,500 unique valid objects in every repetition. Direct grammar produced a median 1,720, mutation 777.5, and naive rejection 334.5. PDRS found a median 22 of 64 seeded bugs, compared with 8 for direct grammar and 2 for mutation and naive rejection.
9. **Parallel work:** Exact rank partitioning had zero overlap. Four independent grammar workers had median overlap of 15.4 percent.
10. **Evolution:** Appending a branch preserved every existing rank. Inserting a branch first or reversing root order changed every existing rank. Expanding an early branch changed 97.5 percent.
11. **Faults:** A median 92.8 percent of raw dense-rank single-bit flips decoded to another valid object. Dense ranks therefore need an integrity layer. A checksum or MAC detects all single-bit alterations in the tested model.
12. **Resource controls:** All four configured resource-exhaustion attacks were rejected quickly.
13. **Timing:** The Python reference implementation is not constant time. Branch-index timing dependence was measurable, especially in unranking.
14. **Domain permutation:** No permutation or inverse failure occurred across four domains. Authentication rejected every tampered tag. Mean avalanche was 0.478, but the construction remains research-only.

## Correctness and proof evidence

The mathematical proof is in `theory/proofs.md`. It establishes finite positive cardinality, disjoint contiguous sibling intervals, rank bounds, both inverse identities, uniformity, exact worker partitioning, complexity, rank-instability counterexamples, and domain-permutation composition.

The independent executable Python model checker does not reuse the PDRS ranking algorithm. It naively enumerates each generated tree in canonical order and checks that count, rank, and unrank match that independent specification.

The C and Rust engines provide a second level of implementation independence. Both consume `PDRS_IR_V1`, independently parse and validate the finite graph, compute subtree cardinalities, and implement rank and unrank. Exhaustive checks cover every object in each of the seven committed schemas. Deterministic vector files separately compare Python, C, and Rust results over 22,096 ranks.

## Native implementation results

The seven static domains contain 194,877 objects in total. Exhaustively checking both native engines gives:

\[
2 \times 194{,}877 = 389{,}754
\]

native round trips. Every one succeeded.

The native evidence is intentionally stricter than a benchmark-only port:

- C uses C11, strict warnings promoted to errors, AddressSanitizer, and UndefinedBehaviorSanitizer.
- Rust uses the stable toolchain, `cargo fmt`, Clippy with `-D warnings`, and the optimized release profile.
- Both engines are compared with the Python canonical implementation on deterministic rank vectors.
- Raw timings, processed speedups, generated IR, vectors, figures, and checksums are committed.

The recorded median speedups are large enough to remove the Python prototype as a practical throughput objection for the supported native domain class. They are not universal constants. They depend on runner hardware, compiler versions, process layout, and the current implementations.

## Density results

PDRS is strongest when branch subdomains are highly imbalanced or when early choices change the remainder of the schema. It cannot improve on a field encoding that is already globally optimal. The two-year calendar is such a case: both PDRS and the local UPER subset use 10 bits.

The compiler AST receives the largest local-packing gain in the static corpus: 18 PDRS bits versus 21.84 average UPER-subset bits. The benefit comes from the very large call-expression subtree and much smaller literal and variable subtrees.

## Fuzzing interpretation

The strongest result is exact nonrepetition. PDRS can address the valid domain directly, select ranks without replacement, divide rank intervals among workers, and reproduce a failure from one rank. Direct grammar remains useful when branch-level rather than object-level balance is desired, but it is biased relative to the object domain and repeats heavily.

The bug experiment seeds bugs uniformly over the valid object domain. Therefore object-uniform PDRS sampling is aligned with the target distribution. Different bug distributions may favor a targeted or weighted grammar. This is a boundary, not a defect hidden from the results.

## Negative results and boundaries

- PDRS fixed ranks save little or nothing against local field packing on balanced product domains.
- Whole-domain ranks are not stable identifiers under arbitrary schema edits.
- Raw dense ranks are poor error-detecting codes.
- The Python implementation leaks timing information and must not be called constant time.
- The cryptographic adapter proves invertibility and measures diffusion, but does not establish standard-grade cryptographic security.
- Uniform rank sampling is not automatically optimal for branch coverage or nonuniform real-world object distributions.
- Native engines currently consume a canonical IR generated from validated JSON rather than independently implementing the complete JSON schema front end.
- Native domain cardinalities are currently restricted to unsigned 64-bit values. The Python reference remains the arbitrary-precision implementation.
- Native performance results are environment dependent and should be reproduced on target hardware before operational claims are made.

## Reproducibility

Raw data is in `results/raw`, derived tables in `results/processed`, figures in `results/figures`, generated native inputs in `native/generated`, and checksums in `results/processed/SHA256SUMS.csv`. Runtime metadata is recorded separately because performance results cannot be byte-identical across hardware.

The permanent native workflow rebuilds both engines, repeats sanitizer and lint gates, regenerates cross-language evidence, and uploads the resulting artifacts on relevant changes.
