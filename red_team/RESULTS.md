# Red-team results

## Controls that held

- cycles are rejected
- missing and unreachable nodes are rejected
- duplicate choice labels are rejected
- maximum node, depth, range-width, and domain-bit limits reject adversarial schemas
- all supported static and generated schemas preserve rank/unrank bijection
- domain permutation remained bijective in every checked domain
- every altered authentication tag was rejected

## Confirmed weaknesses

### Rank churn

Early insertion and root reordering can change 100 percent of existing ranks. Ranks must always be bound to a schema hash and version.

### Fault propagation

The median valid-corruption rate for one-bit rank errors was 92.8 percent. A raw rank is not an integrity-protected serialization.

### Timing

The Python reference implementation is not constant time. Unranking branch position showed statistically significant timing dependence in the recorded run.

### Small domains

A finite-domain permutation does not increase the entropy of the underlying object space. Small domains remain enumerable and deterministic encryption leaks equality under a reused tweak.

### Model boundary

Exact compilation is currently limited to finite acyclic choices and bounded ranges. Arbitrary predicates may turn counting into a computationally hard problem.
