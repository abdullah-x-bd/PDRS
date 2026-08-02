# Native PDRS implementations

This directory contains independent C11 and Rust 2021 implementations of the finite acyclic PDRS core.

Both engines consume `PDRS_IR_V1`, a small canonical intermediate representation generated from the validated JSON schema by `scripts/native_evidence.py prepare`. They independently parse the graph, reject missing, cyclic, and unreachable nodes, compute exact subtree counts, and implement rank and unrank.

The evidence workflow performs:

- exhaustive native round trips over every object in all seven committed schemas
- cross-language comparison against Python on deterministic conformance vectors
- C compilation with strict warnings and AddressSanitizer plus UndefinedBehaviorSanitizer
- Rust Clippy with warnings denied
- per-schema rank and unrank benchmarks for Python, C, and Rust
- generation of raw CSV data, processed summaries, and figures

Current native cardinalities are limited to unsigned 64-bit domains. The Python reference continues to support arbitrary-precision cardinalities.
