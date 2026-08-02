# Architecture

## Layers

1. `Schema` describes ordered finite fields.
2. `SchemaCompiler` converts the schema into a shared acyclic PDRS graph.
3. `Space` exposes rank, unrank, sampling, conditioning, and partitions.
4. `Runner` executes application functions with exact checkpoints.
5. Adapters convert plain records into finance-library or protocol objects.

## State sharing

The compiler does not blindly expand the full Cartesian tree. It computes which prior fields can influence each suffix and memoizes equivalent suffix states.

For example, if `strike` is independent of `currency`, all currency paths can share the same strike suffix graph.

## Branch labels

The PDRS engine receives stable integer-index labels encoded as strings. User values remain in the high-level schema and are converted at the `Space` boundary. This permits finite floats and booleans without relying on backend-specific label serialization.

## Hashes

- `schema_hash` identifies the public FinSpace schema.
- `engine_hash` identifies the exact compiled PDRS graph.

Both should be retained in long-lived evidence and checkpoints.

## Complexity

Compilation is proportional to the number of distinct dependency contexts rather than the number of complete objects. Rank and unrank are proportional to active field depth plus branch lookup costs in the PDRS engine.
