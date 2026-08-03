# PDRS arXiv v3 Phase 10–18 artifact

This directory contains the representation, integrity, mutation, canonicalization, replay, figure, and manuscript revision for **PDRS: A Cross-Language Compiler for Rank-Addressable Finite Structured Domains**.

## Reproduce

```bash
python -m pip install -r requirements-lock.txt
make reproduce
```

The complete networked CI additionally installs `asn1tools` and `dd`, runs the actual ASN.1 PER and external BDD checks, executes the Rust mutant harness, builds the 25-page manuscript, audits claims, and packages the arXiv source.

## Evidence boundaries

Dense ranks attain the minimum fixed-width schema-relative identity length. They are not a self-contained interchange format and provide weak intrinsic corruption detection. Object-uniform sampling is not universally optimal. Coordinated rank intervals are not uniquely capable of zero overlap. Exact object reconstruction does not guarantee execution-result reproduction.

The permanent Zenodo DOI is intentionally absent until Zenodo archives an immutable release and returns a resolving DOI.
