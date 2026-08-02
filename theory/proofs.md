# Proofs for finite acyclic Path-Dependent Radix Spaces

## 1. Model

A finite acyclic PDRS schema is a tuple

\[
\mathcal S=(Q,q_0,A,\delta,F,\prec),
\]

where `Q` is a finite set of states, `q_0` is the root, every nonterminal state has a finite ordered local alphabet `A(q)`, `delta(q,a)` is a deterministic transition, `F` is the set of terminal states, and the reachable transition graph is acyclic. A valid object from state `q` is a finite labelled path ending in `F`.

For a terminal state, define

\[
C(q)=1.
\]

For a nonterminal state, define

\[
C(q)=\sum_{a\in A(q)}C(\delta(q,a)).
\]

A bounded integer range is equivalent to an ordered local alphabet whose labels are the permitted integers. The implementation stores ranges compactly and multiplies the continuation count by the range width.

## 2. Finite positive cardinality

**Theorem 1.** For every reachable state `q`, `C(q)` is a finite positive integer.

**Proof.** Because the reachable graph is finite and acyclic, it has a reverse topological order. For a terminal state, `C(q)=1`, which is finite and positive. Assume every successor of a nonterminal state has finite positive cardinality. Its alphabet is finite and nonempty, so the finite sum of the positive successor cardinalities is finite and positive. Reverse topological induction proves the result for every reachable state, including `q_0`. QED.

## 3. Sibling intervals

For each state `q` and choice `a`, define its offset

\[
O_q(a)=\sum_{b\prec a}C(\delta(q,b)).
\]

Define the interval assigned to `a` as

\[
I_q(a)=\left[O_q(a),O_q(a)+C(\delta(q,a))\right).
\]

**Lemma 2.** Sibling intervals are pairwise disjoint, ordered, contiguous, and their union is `[0,C(q))`.

**Proof.** List the choices in order as `a_0,...,a_{k-1}` and write `c_i=C(delta(q,a_i))`. The interval for `a_i` begins at `sum_{j<i} c_j` and ends at `sum_{j<=i} c_j`. Therefore each interval begins exactly where its predecessor ends, all lengths are positive, and the final endpoint is `sum_i c_i=C(q)`. QED.

## 4. Rank definition and bounds

Define rank recursively. A terminal object has rank zero. For a nonterminal object beginning with choice `a` and continuation `x`,

\[
R_q(a::x)=O_q(a)+R_{\delta(q,a)}(x).
\]

For a range value `v` with lower bound `l`, continuation count `B`, and suffix `x`, this is

\[
R_q(v::x)=(v-l)B+R_{\delta(q,v)}(x).
\]

**Theorem 3.** Every valid object `x` from state `q` satisfies

\[
0\le R_q(x)<C(q).
\]

**Proof.** By induction on remaining path length. The terminal case is `0<=0<1`. In the nonterminal case, the induction hypothesis places the suffix rank in `[0,C(delta(q,a)))`. Adding `O_q(a)` places the full rank in the sibling interval `I_q(a)`, which is contained in `[0,C(q))` by Lemma 2. QED.

## 5. Unrank definition

For `n` in `[0,C(q))`, Lemma 2 gives exactly one choice `a` whose interval contains `n`. Define

\[
U_q(n)=a::U_{\delta(q,a)}(n-O_q(a)).
\]

At a terminal state, `U_q(0)` is the empty path.

## 6. Mutual inverse theorem

**Theorem 4.** For every valid object `x`,

\[
U_q(R_q(x))=x.
\]

**Proof.** By induction on path length. The terminal case is immediate. Write a nonterminal object as `a::x'`. By Theorem 3, `R_{delta(q,a)}(x')` lies within the length of `I_q(a)`. Therefore `R_q(a::x')` lies in exactly `I_q(a)`, so unranking selects `a`, subtracts `O_q(a)`, and recursively receives `R_{delta(q,a)}(x')`. The induction hypothesis returns `x'`. QED.

**Theorem 5.** For every integer `n` in `[0,C(q))`,

\[
R_q(U_q(n))=n.
\]

**Proof.** By induction on the maximum remaining path length. The terminal case has only `n=0`. Otherwise, Lemma 2 identifies a unique interval `I_q(a)` containing `n`. Unranking chooses `a` and remainder `n-O_q(a)`. By the induction hypothesis, ranking the recursively unranked suffix returns that remainder. Adding `O_q(a)` returns `n`. QED.

**Corollary 6.** Rank is a bijection between the valid object set and the integer interval `[0,C(q_0))`.

## 7. Uniform sampling

**Corollary 7.** If `N` is uniform on `[0,C(q_0))`, then `U_{q_0}(N)` is uniform over valid objects.

**Proof.** By Corollary 6, each valid object has exactly one preimage under unrank. Thus every object has probability `1/C(q_0)`. QED.

This result is stronger than a statistical test. The uniformity experiment checks the random-number implementation and the measurement pipeline, not the theorem itself.

## 8. Disjoint parallel partitions

For `w` workers and worker index `i`, define

\[
P_i=\left[\left\lfloor\frac{iC}{w}\right\rfloor,
\left\lfloor\frac{(i+1)C}{w}\right\rfloor\right).
\]

**Theorem 8.** The worker intervals are disjoint, contiguous, and their union is `[0,C)`.

**Proof.** The end of `P_i` is the start of `P_{i+1}`. Monotonicity of floor applied to increasing multiples of `C/w` gives nonnegative interval lengths. The first start is zero and the last end is `floor(wC/w)=C`. QED.

Through the rank bijection, this gives exact nonoverlapping partitions of the object domain.

## 9. Complexity

Let `V` be reachable states, `E` transitions, `d` path depth, and `b` the maximum choice branching factor.

- Validation and topological ordering take `O(V+E)` time and `O(V+E)` memory.
- Exact subtree counting takes `O(V+E)` arbitrary-precision arithmetic operations.
- Ranking takes `O(d)` dictionary lookups and integer operations after compilation.
- Unranking takes `O(d log b)` branch selection with cumulative endpoints and binary search.
- Space after compilation is `O(V+E)` plus arbitrary-precision cardinalities.

The bit complexity of arithmetic also depends on `log C(q_0)`. The scalability experiments report this separately as domain bit length.

## 10. Schema evolution counterexample

Dense ranks cannot be unconditionally stable under arbitrary insertions. Consider a schema whose first branch occupies `[0,m)` and second branch occupies `[m,m+n)`. Insert a new first branch of size `k`. Every old rank moves by `k`. Thus all unchanged objects churn even though their semantic paths remain valid. Appending at the end preserves all existing ranks. The quantified evolution experiment generalizes these boundary cases.

## 11. Structured-domain permutation composition

Let `R:D -> [0,N)` be the PDRS rank bijection, `U=R^{-1}`, and let `P_K` be any permutation on `[0,N)`. Define

\[
E_K=U\circ P_K\circ R.
\]

**Theorem 9.** `E_K` is a permutation on `D`, with inverse

\[
E_K^{-1}=U\circ P_K^{-1}\circ R.
\]

**Proof.** It is a composition of bijections. Direct composition gives

\[
(U P_K^{-1} R)(U P_K R)=U P_K^{-1}(RU)P_K R=U P_K^{-1}P_K R=UR=\mathrm{id}_D.
\]

The reverse composition is identical. QED.

This theorem proves format preservation and invertibility, not the security of a particular `P_K`. The included Feistel adapter is research evidence only and is explicitly not presented as a standardized deployment primitive.

## 12. Executable verification

`scripts/verify_theorems.py` uses an independent naive enumerator to exhaustively compare object order, count, rank, and unrank across generated finite trees. This checks the implementation against a second executable specification. It complements but does not substitute for the general proofs above.
