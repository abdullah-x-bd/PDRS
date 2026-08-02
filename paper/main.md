# Path-Dependent Radix Spaces

## Canonical Ranking and Compilation of Heterogeneous Finite Domains

### Abstract

Structured records frequently contain dependent fields: an early choice determines which later fields exist and which values are valid. Conventional field-oriented encodings often represent a superset of the valid object space, while ad hoc generators struggle to sample valid objects uniformly or partition testing without overlap. We define finite acyclic Path-Dependent Radix Spaces, a state-based representation in which each valid object is a path and each branch occupies a contiguous interval proportional to its number of valid completions. This yields an exact bijection between a constrained object domain and an integer interval. We present a reference compiler supporting ordered choices and bounded integer ranges, prove the core rank/unrank properties, and establish a reproducible evaluation programme for encoding density, uniform structured fuzzing, schema evolution, and cryptographic domain adaptation. We explicitly position the work as a synthesis and systems contribution building on mixed-radix numeration, dynamic radix systems, enumerative coding, dependent data types, and format-preserving encryption.

## 1. Introduction

The motivating observation is that a positional scale need not remain constant. In a structured record, the number of valid next choices may depend on the path already taken. The central question is not whether such representations exist, because substantial prior art does, but whether a practical compiler can make a finite dependent schema simultaneously usable for exact counting, canonical serialization, uniform generation, reproducible fuzzing, and safe domain adaptation.

## 2. Related work

Required comparison areas:

- fixed and mixed-radix numeration
- dynamic radix numeration systems
- enumerative source encoding
- abstract numeration systems
- dependent sums and finite dependent types
- ASN.1 Packed Encoding Rules
- schema-driven serialization
- grammar-based and property-based fuzzing
- rank-then-encipher and format-preserving encryption

The paper will not claim novelty for mixed radix, dynamic radix, or ranking constrained sets.

## 3. Model

See `theory/definitions.md`. The paper will state the finite acyclic schema, subtree cardinality, branch intervals, rank, unrank, schema identity, and the exact supported language.

## 4. Algorithms and implementation

The reference compiler validates the graph, rejects cycles and ambiguity, caches subtree counts, and implements rank and unrank in time proportional to path length plus branch selection cost.

## 5. Evaluation

See `paper/sections/evaluation_plan.md` and experiment manifests.

## 6. Robustness and limitations

The primary limitations are computational hardness for richer predicates, rank instability under schema evolution, poor error locality, absence of an intrinsic probability model, and the need for established cryptographic primitives for any encryption use.

## 7. Conclusion

The intended contribution is a rigorous, reproducible compiler framework for finite path-dependent domains, not a replacement foundation for arithmetic and not a hidden-base cipher.
