# Path-Dependent Radix Spaces

PDRS compiles a finite dependent schema into an exact integer domain. Every valid structured object has one canonical rank in `0..N-1`, and every rank decodes to exactly one valid object.

The public Python distribution is **PDRS 0.2.0**. The repository also contains a later **evidence revision 0.3** with independent C11 and Rust 2021 implementations, cross-language conformance data, comparative experiments, and the arXiv v2 research revision. Package versions identify installable releases; commit SHAs identify exact evidence.

## Verified core

- exact subtree cardinality
- canonical rank and unrank
- finite acyclic DAG support
- deterministic schema hashes
- uniform sampling by rank
- exact disjoint worker partitions
- iterative validation for deep schemas
- explicit node, depth, range, and domain-bit limits
- independent Python, C, and Rust implementations

## Evidence bundle

The committed historical evidence covers 254,609 Python checks, 389,754 native round trips, 22,096 cross-language vectors, encoding and runtime measurements, structured-generation comparisons, schema-evolution and fault-propagation studies, and finance-facing real-program evaluations. The arXiv v2 revision adds fair multi-distribution defect experiments, coordinated distributed baselines, typed lowering conditions, bit-complexity analysis, direct SciFe and knowledge-compilation positioning, and a surgically revised paper.

Read [`docs/EVIDENCE_REPORT.md`](docs/EVIDENCE_REPORT.md), [`results/real_program/RESULTS.md`](results/real_program/RESULTS.md), and the arXiv revision status when it lands under `paper/arxiv_v2/`.

## Reproduction

```bash
python -m pip install -r requirements-experiments.txt
PYTHONPATH=src python -m unittest discover -s tests -v
```

The arXiv v2 evidence workflow separately executes the expanded QuantLib, SimpleFIX, and ISO 20022 campaign before those new numerical results enter the manuscript.

## Important boundaries

- The proofs apply to the declared finite acyclic choice/range/terminal schema class.
- The ranking construction follows established indexed and dependent enumeration work.
- Python supports arbitrary-precision cardinalities; native engines currently use unsigned 64-bit cardinalities.
- Object-uniform sampling is not branch-balanced or universally optimal for defect discovery.
- Equal-size contiguous rank intervals do not guarantee equal execution cost.
- Dense ranks require an outer checksum or authentication layer for integrity.
- Rank stability under schema evolution is conditional.
- Object replay requires a fixed canonicalization version and schema identity; execution replay additionally requires the adapter, environment, oracle, and external-data state.
- No previously unknown defect was confirmed in the accepted historical real-program campaign.
