# Formal definitions

## Finite acyclic path-dependent radix schema

A schema is a tuple:

```math
\mathcal S=(Q,q_0,A,\delta,F,\prec)
```

where:

- `Q` is a finite set of states
- `q_0` is the initial state
- `A(q)` is a finite set of choices available at state `q`
- `delta(q,a)` is a deterministic transition
- `F` is the set of terminal states
- `prec_q` is a total order over `A(q)`
- the reachable transition graph is acyclic

A valid object is a path from `q_0` to a terminal state.

## Subtree cardinality

For terminal `q`:

```math
C(q)=1.
```

For nonterminal `q`:

```math
C(q)=\sum_{a\in A(q)}C(\delta(q,a)).
```

## Rank

For path `a_0,...,a_{n-1}`, the contribution at state `q_i` is:

```math
O(q_i,a_i)=\sum_{b\prec_{q_i}a_i}C(\delta(q_i,b)).
```

The rank is the sum of those offsets along the selected path.

A bounded integer range node is syntactic sugar for an ordered set of branches that all transition to the same target.

## Nonclaims

The schema is not a cryptographic key. Canonical ranking is not encryption. Transporting ordinary integer arithmetic through rank and unrank does not create a new algebraic structure.
