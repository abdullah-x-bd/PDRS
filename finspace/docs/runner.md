# Checkpointed runner

`Runner` executes an application function over exact ranks.

```python
runner = Runner(
    space,
    calculate,
    backend="thread",
    max_workers=8,
    checkpoint="results.sqlite",
    run_id="daily-risk",
)
summary = runner.run(partition=space.partition(0, 4))
```

## Backends

- `sequential` is deterministic and easiest to debug.
- `thread` is appropriate for I/O or native libraries that release the GIL.
- `process` is appropriate for picklable CPU-bound Python functions.

## Checkpoint semantics

Completed ranks are stored in SQLite and skipped on resume. Failed ranks remain eligible for a later retry. The checkpoint records:

- run ID
- schema hash
- engine hash
- integer rank
- status
- JSON result
- traceback
- elapsed time

A run ID cannot be reused with a different schema.

## Result restrictions

Checkpointed results must be JSON serializable. Convert complex finance objects to plain dictionaries, numbers, strings, and lists before returning them.

## Distributed deployment

Use one checkpoint per worker or a database service with application-level coordination. SQLite is designed for reliable local checkpointing, not simultaneous writes from many machines.
