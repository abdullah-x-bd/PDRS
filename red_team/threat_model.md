# Threat and robustness model

## Protected properties

- canonicality of schema interpretation
- collision-free rank mapping
- total unrank over the stated interval
- resource-bounded compilation and execution
- explicit schema-version binding
- integrity of generated artifacts

## Adversarial inputs

- cyclic schemas
- missing targets
- duplicate labels
- unreachable nodes
- enormous ranges
- deeply nested paths
- schema substitutions
- corrupted ranks
- branch-order changes
- arbitrary cross-field constraints in future language versions

## Known structural risks

### Rank churn

Inserting choices before an existing branch shifts the contiguous interval assigned to later branches. A rank is therefore meaningful only together with a schema version or canonical hash.

### Resource exhaustion

The current model uses arbitrary-precision Python integers. Future implementations need limits on node count, range width, domain bits, recursion depth, and generated output.

### Dense-code corruption

A bit flip in a dense rank can decode to a different valid object. Transmission formats require checksums or authenticated encryption.

### Cryptographic misuse

The schema and radix schedule are public structure. Security must derive from an established cryptographic primitive, nonce or tweak discipline, key separation, and integrity protection.
