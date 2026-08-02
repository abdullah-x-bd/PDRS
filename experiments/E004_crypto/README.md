# E004: Cryptographic domain adapter

Planned construction:

```math
C=\operatorname{unrank}(P_{K,T,N}(\operatorname{rank}(M))).
```

The experiment will use an established keyed permutation or FPE construction. It will not treat a secret radix or branch order as the source of security.

Required evaluation:

- exact domain-size safety gate
- tweak and version binding
- ciphertext validity
- equality leakage analysis
- integrity composition
- timing analysis
- schema-confusion tests
