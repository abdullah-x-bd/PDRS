# Core theorem programme

## Theorem T1: finite cardinality

For a finite reachable acyclic schema, `C(q)` is a finite positive integer for every reachable state.

Proof strategy: reverse topological induction.

## Theorem T2: rank bounds

For every valid object `x`:

```math
0\leq \operatorname{rank}_{\mathcal S}(x)<C(q_0).
```

Proof strategy: induction over the selected path and disjoint contiguous sibling intervals.

## Theorem T3: rank and unrank are mutual inverses

For every valid object `x`:

```math
\operatorname{unrank}_{\mathcal S}(\operatorname{rank}_{\mathcal S}(x))=x.
```

For every integer `n` in the rank domain:

```math
\operatorname{rank}_{\mathcal S}(\operatorname{unrank}_{\mathcal S}(n))=n.
```

The implementation exhaustively checks these identities on the committed small schemas and generated domains.

## Corollary T4: uniform sampling

If `R` is uniform on `0..C(q_0)-1`, then `unrank(R)` is uniform over the valid object domain.

## Open theorem questions

- Characterize cyclic schemas with finite valid languages.
- Characterize schemas whose successor relation is regular.
- Determine when native addition is finite-state computable.
- Bound rank churn under local schema edits.
- Bound compilation complexity for richer predicate languages.
