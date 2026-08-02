from __future__ import annotations

from collections import Counter

from finspace import Field, Schema, Space


def space() -> Space:
    return Space(
        Schema(
            name="sampling",
            fields=(
                Field.enum("kind", ("small", "large")),
                Field.dependent(
                    "value",
                    "kind",
                    {"small": tuple(range(2)), "large": tuple(range(20))},
                ),
            ),
        )
    )


def test_sample_without_replacement_is_unique_and_reproducible() -> None:
    domain = space()
    first = domain.sample(15, replace=False, seed=42, with_ranks=True)
    second = domain.sample(15, replace=False, seed=42, with_ranks=True)
    assert first == second
    assert len({rank for rank, _ in first}) == 15


def test_stratified_sample_balances_root_field() -> None:
    domain = space()
    records = domain.sample_stratified("kind", 4, seed=42)
    assert Counter(record["kind"] for record in records) == {"small": 2, "large": 2}


def test_partitions_are_disjoint_and_complete() -> None:
    domain = space()
    partitions = domain.partitions(7)
    ranks = [rank for partition in partitions for rank in partition]
    assert ranks == list(range(domain.count))
    assert sum(len(partition) for partition in partitions) == domain.count


def test_partition_batches() -> None:
    partition = space().partition(0, 2)
    batches = list(partition.batches(3))
    assert sum(len(batch) for batch in batches) == len(partition)
