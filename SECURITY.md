# Security policy

PDRS is a research prototype. It is not a production encryption library.

Please report security-sensitive findings privately to the repository owner. Include the affected schema, commit, reproduction steps, and expected consequence.

The following are in scope for research disclosure:

- rank or unrank collisions
- malformed-schema acceptance
- integer or memory exhaustion
- timing or state-dependent leakage
- unsafe cryptographic composition
- deterministic equality leakage
- schema-version confusion

The project makes no claim that secrecy of a radix, branch order, or schema provides cryptographic security.
