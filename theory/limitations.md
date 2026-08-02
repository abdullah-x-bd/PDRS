# Limitations and boundary conditions

1. **Acyclic only.** The reference compiler rejects cycles rather than attempting bounded or regular-language analysis.
2. **Finite only.** Every schema must have an exactly countable finite domain.
3. **No arbitrary predicates.** General cross-field predicates can reduce exact counting to computationally hard problems.
4. **Rank instability.** Inserting an early branch can change the ranks of many unchanged objects.
5. **No semantic metric.** Equal radix counts do not imply similarity between choices.
6. **No probability model.** Canonical ranking treats valid objects uniformly and is not an entropy coder for nonuniform data.
7. **Error propagation.** A corrupted dense rank may decode to a different valid object.
8. **No cryptographic security.** Encryption requires a separate, established keyed permutation and integrity mechanism.
9. **Arbitrary precision.** Large domains may require large integers and careful resource limits.
10. **Ordering dependence.** Canonical ranks depend on a versioned branch ordering.
