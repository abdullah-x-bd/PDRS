# Research roadmap

## M0: Scope and prior art

- [x] Establish terminology and nonclaims
- [x] Create source registry and prior-art matrix
- [x] Define claim-evidence ledger
- [ ] Complete systematic literature review
- [ ] Obtain independent novelty review

## M1: Mathematical foundation

- [x] Define finite acyclic path-dependent radix schemas
- [x] Implement exact subtree counting
- [x] Implement canonical rank and unrank
- [x] State bijection and uniform-sampling theorems
- [x] Exhaustively test small domains
- [ ] Produce machine-checked proof of the core bijection
- [ ] Characterize finite-state successor and addition

## M2: Reference compiler

- [x] JSON schema format
- [x] Python reference implementation
- [x] Command-line interface
- [x] Canonical schema digest
- [ ] Bounded lists and optional fields as first-class syntax
- [ ] DAG sharing and compiler optimization
- [ ] Rust implementation
- [ ] Generated codecs

## M3: Benchmark corpus

- [x] Permit schema
- [x] Calendar schema
- [x] AI action schema
- [x] Synthetic fixed-radix generator
- [ ] Telecom protocol corpus
- [ ] Compiler AST corpus
- [ ] Administrative code corpus

## M4: Comparative evidence

- [x] Deterministic density benchmark
- [ ] Runtime benchmark with controlled hardware
- [ ] ASN.1 PER baseline
- [ ] Protocol Buffers baseline
- [ ] Rejection-sampling baseline
- [ ] Grammar-fuzzer baseline
- [ ] Statistical uniformity study

## M5: Red team

- [x] Initial threat and assumption registry
- [x] Cycle, ambiguity, and malformed-schema tests
- [ ] State-explosion benchmark
- [ ] Rank-churn experiment
- [ ] Fault-propagation experiment
- [ ] Side-channel analysis
- [ ] Independent reviewer challenge set

## M6: Paper

- [x] Manuscript skeleton
- [x] Evaluation plan
- [ ] Complete related work
- [ ] Complete formal results
- [ ] Complete experiments
- [ ] Freeze artifact and draft paper
