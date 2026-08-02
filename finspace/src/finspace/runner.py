"""Checkpointed execution over exact FinSpace ranks."""

from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, ProcessPoolExecutor, ThreadPoolExecutor, wait
from dataclasses import dataclass
import itertools
import json
from pathlib import Path
import sqlite3
import time
import traceback
from typing import Any, Callable, Iterable, Iterator, Literal, Mapping

from .errors import CheckpointError
from .space import Partition, Space

Backend = Literal["sequential", "thread", "process"]


def _default_json(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    raise TypeError(f"value of type {type(value).__name__} is not JSON serializable")


@dataclass(frozen=True)
class TaskResult:
    rank: int
    status: Literal["completed", "failed", "skipped"]
    result: Any = None
    error: str | None = None
    seconds: float = 0.0


@dataclass(frozen=True)
class RunSummary:
    run_id: str
    schema_hash: str
    submitted: int
    completed: int
    failed: int
    skipped: int
    seconds: float
    checkpoint: str | None

    @property
    def successful(self) -> bool:
        return self.failed == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "schema_hash": self.schema_hash,
            "submitted": self.submitted,
            "completed": self.completed,
            "failed": self.failed,
            "skipped": self.skipped,
            "seconds": self.seconds,
            "checkpoint": self.checkpoint,
            "successful": self.successful,
        }


def _execute_function(
    function: Callable[[Mapping[str, Any]], Any],
    rank: int,
    record: Mapping[str, Any],
) -> TaskResult:
    started = time.perf_counter()
    try:
        return TaskResult(
            rank,
            "completed",
            result=function(record),
            seconds=time.perf_counter() - started,
        )
    except Exception as error:
        detail = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        return TaskResult(rank, "failed", error=detail, seconds=time.perf_counter() - started)


class CheckpointStore:
    """SQLite-backed exact-rank checkpoint and result store."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA synchronous=NORMAL")
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                schema_hash TEXT NOT NULL,
                engine_hash TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tasks (
                run_id TEXT NOT NULL,
                rank TEXT NOT NULL,
                status TEXT NOT NULL,
                result_json TEXT,
                error TEXT,
                seconds REAL NOT NULL DEFAULT 0,
                updated_at REAL NOT NULL,
                PRIMARY KEY (run_id, rank),
                FOREIGN KEY (run_id) REFERENCES runs(run_id)
            );
            CREATE INDEX IF NOT EXISTS tasks_status ON tasks(run_id, status);
            """
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "CheckpointStore":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    def ensure_run(self, run_id: str, space: Space) -> None:
        row = self.connection.execute(
            "SELECT schema_hash, engine_hash FROM runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        if row is None:
            self.connection.execute(
                "INSERT INTO runs(run_id, schema_hash, engine_hash, created_at) VALUES (?, ?, ?, ?)",
                (run_id, space.schema_hash, space.engine_hash, time.time()),
            )
            self.connection.commit()
            return
        if row != (space.schema_hash, space.engine_hash):
            raise CheckpointError(
                f"checkpoint run {run_id!r} belongs to schema {row[0]}, not {space.schema_hash}"
            )

    def completed_ranks(self, run_id: str) -> set[int]:
        rows = self.connection.execute(
            "SELECT rank FROM tasks WHERE run_id = ? AND status = 'completed'", (run_id,)
        )
        return {int(row[0]) for row in rows}

    def record(self, run_id: str, task: TaskResult) -> None:
        result_json = None
        if task.status == "completed":
            result_json = json.dumps(task.result, default=_default_json, separators=(",", ":"))
        self.connection.execute(
            """
            INSERT INTO tasks(run_id, rank, status, result_json, error, seconds, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id, rank) DO UPDATE SET
                status = excluded.status,
                result_json = excluded.result_json,
                error = excluded.error,
                seconds = excluded.seconds,
                updated_at = excluded.updated_at
            """,
            (
                run_id,
                str(task.rank),
                task.status,
                result_json,
                task.error,
                task.seconds,
                time.time(),
            ),
        )
        self.connection.commit()

    def results(self, run_id: str, status: str | None = None) -> Iterator[TaskResult]:
        query = "SELECT rank, status, result_json, error, seconds FROM tasks WHERE run_id = ?"
        parameters: list[Any] = [run_id]
        if status is not None:
            query += " AND status = ?"
            parameters.append(status)
        query += " ORDER BY CAST(rank AS INTEGER)"
        for rank, task_status, result_json, error, seconds in self.connection.execute(query, parameters):
            yield TaskResult(
                rank=int(rank),
                status=task_status,
                result=json.loads(result_json) if result_json else None,
                error=error,
                seconds=seconds,
            )


class Runner:
    """Execute a callable over exact ranks with resumable checkpoints.

    Rank iterables are consumed lazily. Even a billion-object partition is not
    materialized as a Python list.
    """

    def __init__(
        self,
        space: Space,
        function: Callable[[Mapping[str, Any]], Any],
        *,
        backend: Backend = "sequential",
        max_workers: int | None = None,
        checkpoint: str | Path | None = None,
        run_id: str = "default",
        fail_fast: bool = False,
        max_in_flight: int | None = None,
    ) -> None:
        if backend not in {"sequential", "thread", "process"}:
            raise ValueError(f"unsupported backend {backend!r}")
        self.space = space
        self.function = function
        self.backend = backend
        self.max_workers = max_workers
        self.checkpoint = Path(checkpoint) if checkpoint is not None else None
        self.run_id = run_id
        self.fail_fast = fail_fast
        self.max_in_flight = max_in_flight

    def _parallel(
        self,
        ranks: Iterable[int],
        executor_type: type[ThreadPoolExecutor] | type[ProcessPoolExecutor],
    ) -> Iterator[TaskResult]:
        iterator = iter(ranks)
        workers = self.max_workers or 4
        capacity = self.max_in_flight or max(1, workers * 4)
        with executor_type(max_workers=self.max_workers) as executor:
            futures: dict[Future[TaskResult], int] = {}

            def submit_one() -> bool:
                try:
                    rank = next(iterator)
                except StopIteration:
                    return False
                record = self.space.unrank(rank)
                future = executor.submit(_execute_function, self.function, rank, record)
                futures[future] = rank
                return True

            for _ in range(capacity):
                if not submit_one():
                    break
            while futures:
                done, _ = wait(futures, return_when=FIRST_COMPLETED)
                for future in done:
                    futures.pop(future)
                    yield future.result()
                    submit_one()

    def run(
        self,
        *,
        ranks: Iterable[int] | None = None,
        partition: Partition | None = None,
        limit: int | None = None,
        resume: bool = True,
    ) -> RunSummary:
        if ranks is not None and partition is not None:
            raise ValueError("provide ranks or partition, not both")
        if limit is not None and limit < 0:
            raise ValueError("limit cannot be negative")
        source: Iterable[int] = (
            ranks if ranks is not None else partition if partition is not None else range(self.space.count)
        )
        if limit is not None:
            source = itertools.islice(source, limit)

        store = CheckpointStore(self.checkpoint) if self.checkpoint else None
        if store:
            store.ensure_run(self.run_id, self.space)
        completed_before = store.completed_ranks(self.run_id) if store and resume else set()
        submitted = 0
        skipped = 0

        def pending() -> Iterator[int]:
            nonlocal submitted, skipped
            for rank in source:
                submitted += 1
                if rank < 0 or rank >= self.space.count:
                    raise ValueError(f"rank {rank} is outside the space")
                if rank in completed_before:
                    skipped += 1
                    continue
                yield rank

        started = time.perf_counter()
        completed = 0
        failed = 0
        if self.backend == "sequential":
            results: Iterable[TaskResult] = (
                _execute_function(self.function, rank, self.space.unrank(rank)) for rank in pending()
            )
        elif self.backend == "thread":
            results = self._parallel(pending(), ThreadPoolExecutor)
        else:
            results = self._parallel(pending(), ProcessPoolExecutor)

        try:
            for task in results:
                if store:
                    store.record(self.run_id, task)
                if task.status == "completed":
                    completed += 1
                else:
                    failed += 1
                    if self.fail_fast:
                        raise RuntimeError(task.error or f"rank {task.rank} failed")
        finally:
            if store:
                store.close()

        return RunSummary(
            run_id=self.run_id,
            schema_hash=self.space.schema_hash,
            submitted=submitted,
            completed=completed,
            failed=failed,
            skipped=skipped,
            seconds=time.perf_counter() - started,
            checkpoint=str(self.checkpoint) if self.checkpoint else None,
        )
