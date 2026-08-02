from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import random
from typing import Callable, Iterable, Sequence

from .core import ChoiceNode, CompiledSchema, RangeNode, SchemaError, TerminalNode, Token


@dataclass
class FuzzRun:
    method: str
    attempts: int
    valid: int
    unique: int
    duplicate: int
    root_branches: int
    nodes_covered: int
    bugs_found: int
    first_bug_attempt: int | None
    ranks: list[int]

    @property
    def validity_rate(self) -> float:
        return self.valid / self.attempts if self.attempts else 0.0

    @property
    def unique_rate(self) -> float:
        return self.unique / self.valid if self.valid else 0.0


def direct_grammar_value(schema: CompiledSchema, rng: random.Random) -> list[Token]:
    node_name = schema.root
    out: list[Token] = []
    while True:
        node = schema.nodes[node_name]
        if isinstance(node, TerminalNode):
            return out
        if isinstance(node, ChoiceNode):
            branch = rng.choice(node.branches)
            out.append(branch.value)
            node_name = branch.target
        else:
            out.append(rng.randint(node.start, node.stop))
            node_name = node.target


def _depth_candidates(schema: CompiledSchema) -> list[list[Token]]:
    current: set[str] = {schema.root}
    candidates: list[list[Token]] = []
    while current:
        next_nodes: set[str] = set()
        values: list[Token] = []
        for name in current:
            node = schema.nodes[name]
            if isinstance(node, TerminalNode):
                continue
            if isinstance(node, ChoiceNode):
                values.extend(branch.value for branch in node.branches)
                next_nodes.update(branch.target for branch in node.branches)
            else:
                # Include the full range for modest ranges and representative values otherwise.
                width = node.stop - node.start + 1
                if width <= 256:
                    values.extend(range(node.start, node.stop + 1))
                else:
                    values.extend(
                        [
                            node.start,
                            node.start + width // 4,
                            node.start + width // 2,
                            node.start + (3 * width) // 4,
                            node.stop,
                        ]
                    )
                next_nodes.add(node.target)
        if values:
            # Preserve type distinctions and stable order while removing duplicates.
            seen: set[tuple[type, Token]] = set()
            deduped: list[Token] = []
            for value in values:
                key = (type(value), value)
                if key not in seen:
                    seen.add(key)
                    deduped.append(value)
            candidates.append(deduped)
        current = next_nodes
    return candidates


def naive_candidate(schema: CompiledSchema, rng: random.Random, candidates: list[list[Token]] | None = None) -> list[Token]:
    candidates = candidates if candidates is not None else _depth_candidates(schema)
    length = rng.randint(1, len(candidates))
    return [rng.choice(candidates[depth]) for depth in range(length)]


def mutate_value(
    schema: CompiledSchema,
    seed_value: Sequence[Token],
    rng: random.Random,
    candidates: list[list[Token]] | None = None,
) -> list[Token]:
    candidates = candidates if candidates is not None else _depth_candidates(schema)
    value = list(seed_value)
    operation = rng.choice(["replace", "replace", "truncate", "extend"])
    if operation == "replace" and value:
        index = rng.randrange(len(value))
        if index < len(candidates):
            value[index] = rng.choice(candidates[index])
    elif operation == "truncate" and value:
        value = value[: rng.randrange(len(value) + 1)]
    elif operation == "extend" and len(value) < len(candidates):
        value.append(rng.choice(candidates[len(value)]))
    return value


def _run_values(
    schema: CompiledSchema,
    method: str,
    candidates: Iterable[Sequence[Token]],
    attempts: int,
    bug_predicate: Callable[[int, Sequence[Token]], bool],
) -> FuzzRun:
    ranks: list[int] = []
    seen: set[int] = set()
    nodes: set[str] = set()
    roots: set[Token] = set()
    bugs: set[int] = set()
    first_bug: int | None = None
    valid = 0
    for attempt, value in enumerate(candidates, start=1):
        if attempt > attempts:
            break
        try:
            rank = schema.rank(value)
            trace = schema.trace(value)
        except SchemaError:
            continue
        valid += 1
        ranks.append(rank)
        seen.add(rank)
        nodes.update(trace)
        if value:
            roots.add(value[0])
        if bug_predicate(rank, value):
            bugs.add(rank)
            if first_bug is None:
                first_bug = attempt
    return FuzzRun(
        method=method,
        attempts=attempts,
        valid=valid,
        unique=len(seen),
        duplicate=max(0, valid - len(seen)),
        root_branches=len(roots),
        nodes_covered=len(nodes),
        bugs_found=len(bugs),
        first_bug_attempt=first_bug,
        ranks=ranks,
    )


def run_fuzz_methods(
    schema: CompiledSchema,
    *,
    budget: int,
    seed: int,
    bug_ranks: set[int],
) -> list[FuzzRun]:
    def bug_predicate(rank: int, _: Sequence[Token]) -> bool:
        return rank in bug_ranks

    rng = random.Random(seed)
    k = min(budget, schema.count)
    pdrs_ranks = rng.sample(range(schema.count), k=k)
    pdrs_values = (schema.unrank(rank) for rank in pdrs_ranks)
    pdrs = _run_values(schema, "pdrs_without_replacement", pdrs_values, k, bug_predicate)

    rng = random.Random(seed)
    grammar_values = (direct_grammar_value(schema, rng) for _ in range(budget))
    grammar = _run_values(schema, "direct_grammar", grammar_values, budget, bug_predicate)

    depth_candidates = _depth_candidates(schema)
    rng = random.Random(seed)
    rejection_values = (naive_candidate(schema, rng, depth_candidates) for _ in range(budget))
    rejection = _run_values(schema, "naive_rejection", rejection_values, budget, bug_predicate)

    rng = random.Random(seed)
    current = schema.unrank(0)

    def mutations():
        nonlocal current
        for _ in range(budget):
            proposal = mutate_value(schema, current, rng, depth_candidates)
            try:
                schema.rank(proposal)
                current = proposal
            except SchemaError:
                pass
            yield proposal

    mutation = _run_values(schema, "mutation", mutations(), budget, bug_predicate)
    return [pdrs, grammar, rejection, mutation]


def parallel_overlap(
    schema: CompiledSchema,
    *,
    workers: int,
    budget_per_worker: int,
    seed: int,
) -> dict[str, float]:
    # PDRS workers receive disjoint contiguous intervals by construction.
    pdrs_sets: list[set[int]] = []
    for worker in range(workers):
        start, stop = schema.partition(worker, workers)
        available = max(0, stop - start)
        take = min(budget_per_worker, available)
        pdrs_sets.append(set(range(start, start + take)))

    grammar_sets: list[set[int]] = []
    for worker in range(workers):
        rng = random.Random(seed + worker)
        ranks = {
            schema.rank(direct_grammar_value(schema, rng))
            for _ in range(budget_per_worker)
        }
        grammar_sets.append(ranks)

    def overlap_fraction(groups: list[set[int]]) -> float:
        total = sum(len(group) for group in groups)
        union = len(set().union(*groups)) if groups else 0
        return (total - union) / total if total else 0.0

    return {
        "pdrs_overlap_fraction": overlap_fraction(pdrs_sets),
        "grammar_overlap_fraction": overlap_fraction(grammar_sets),
        "pdrs_union": len(set().union(*pdrs_sets)),
        "grammar_union": len(set().union(*grammar_sets)),
    }
