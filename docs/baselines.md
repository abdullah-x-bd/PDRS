# Experimental baselines

## PDRS fixed-rank encoding

The theoretical fixed-length representation uses `ceil(log2 N)` bits for a domain of size `N`. The byte representation rounds this width to whole octets.

## UPER subset

The experiment implements the directly relevant unaligned Packed Encoding Rules subset:

- an ordered `CHOICE` is encoded using `ceil(log2 k)` bits for `k` alternatives
- a fully constrained whole number is encoded using `ceil(log2 width)` bits
- fields are encoded along the selected path without octet alignment

This is a faithful benchmark for the supported PDRS node types, but it is not claimed to implement every rule in ITU-T X.691.

## Protocol Buffers wire baseline

Every selected choice index or bounded integer offset is encoded as a protobuf varint field. Field numbers correspond to path positions. The resulting bytes follow the protobuf wire format. It is a generic schema-independent baseline and may be larger than a separately hand-optimized `.proto` for a specific application.

## Naive fixed-field allocation

For every path depth, allocate enough bits for the largest local alphabet at that depth. A sentinel is added when some objects terminate before that depth. This represents the natural rectangular superset that PDRS is designed to avoid.

## Compact JSON

The object token list is encoded with compact separators and UTF-8. It provides a familiar human-readable baseline rather than a compact binary competitor.

## Fuzzing methods

- **PDRS without replacement:** uniformly choose distinct ranks and unrank them.
- **Direct grammar:** choose every local branch uniformly, then choose bounded integers uniformly.
- **Naive rejection:** generate tokens from depth-wise global supersets and reject invalid objects.
- **Mutation:** mutate a valid seed one token at a time and retain valid proposals.

PDRS is compared as a rank-addressable generation method, not merely as sampling with replacement.
