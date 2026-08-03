# PDRS arXiv v2 research artifact

This directory implements the Phase 1–9 revision programme for the manuscript **PDRS: A Cross-Language Compiler for Rank-Addressable Finite Structured Domains**.

## Reproduce the synthetic evidence and paper

```bash
python -m pip install -r requirements-lock.txt
make reproduce
```

The run produces:

- semantic-correctness evidence
- compilation and rank/unrank scaling evidence
- eight-distribution defect-discovery evidence
- distributed allocation and load-balance evidence
- paired campaign-level bootstrap intervals
- four publication figures
- a compiled PDF manuscript
- SHA-256 checksums

## Directory map

- `src/` typed audit compiler and reduced-MDD baseline
- `tests/` semantic and partition tests
- `experiments/` deterministic Phase 1–8 pipeline
- `real_program/` Phase 9 external-program extension
- `results/` generated raw and processed evidence
- `figures/` generated paper figures
- `paper/` LaTeX manuscript and bibliography
- `reproducibility/` freeze manifest, checksums, and archive instructions

## Claim discipline

The artifact treats counting, ranking, unranking, and indexed dependent enumeration as established ideas. It evaluates PDRS as a systems realization with an external schema, canonical IR, independent runtimes, operational allocation, and a finance-oriented layer. It removes the Pareto-frontier claim and does not claim universal bug-finding superiority.

The real-program workflow records boundary, conformance, and parser behavior. It does not label an observation as a previously unknown defect without independent upstream confirmation.
