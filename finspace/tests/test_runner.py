from __future__ import annotations

from finspace import Field, Schema, Space
from finspace.runner import CheckpointStore, Runner


def square(record):
    return {"square": record["value"] ** 2}


def test_checkpoint_resume(tmp_path) -> None:
    space = Space(Schema(name="runner", fields=(Field.enum("value", tuple(range(10))),)))
    checkpoint = tmp_path / "results.sqlite"
    runner = Runner(space, square, checkpoint=checkpoint, run_id="test")
    first = runner.run(ranks=range(5))
    assert first.completed == 5
    assert first.skipped == 0
    second = runner.run(ranks=range(10))
    assert second.completed == 5
    assert second.skipped == 5
    with CheckpointStore(checkpoint) as store:
        results = list(store.results("test", "completed"))
    assert len(results) == 10
    assert results[3].result == {"square": 9}


def test_thread_backend() -> None:
    space = Space(Schema(name="threads", fields=(Field.enum("value", tuple(range(20))),)))
    summary = Runner(space, square, backend="thread", max_workers=4).run(ranks=range(20))
    assert summary.completed == 20
    assert summary.failed == 0
