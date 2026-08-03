# Dense-rank integrity

A dense rank minimizes schema-relative fixed-width identity length. It does not provide error detection or authenticity. A practical transport record should bind the canonicalization version, schema hash, rank, and integrity field. Checksums address accidental corruption. A MAC addresses authenticity when a key and threat model justify it.
