"""Command-line interface for FinSpace."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Iterable

from .space import Space


def _json(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, default=str)


def _load_record(value: str) -> dict[str, Any]:
    candidate = Path(value)
    raw = json.loads(candidate.read_text(encoding="utf-8")) if candidate.exists() else json.loads(value)
    if not isinstance(raw, dict):
        raise ValueError("record must be a JSON object")
    return raw


def _space(path: str) -> Space:
    return Space.load(path)


def command_inspect(args: argparse.Namespace) -> int:
    print(_json(_space(args.schema).describe()))
    return 0


def command_rank(args: argparse.Namespace) -> int:
    space = _space(args.schema)
    record = _load_record(args.record)
    print(_json(space.explain(record)))
    return 0


def command_unrank(args: argparse.Namespace) -> int:
    space = _space(args.schema)
    print(_json({"rank": args.rank, "record": space.unrank(args.rank)}))
    return 0


def command_validate(args: argparse.Namespace) -> int:
    space = _space(args.schema)
    record = _load_record(args.record)
    rank = space.rank(record)
    print(_json({"valid": True, "rank": rank, "schema_hash": space.schema_hash}))
    return 0


def command_sample(args: argparse.Namespace) -> int:
    space = _space(args.schema)
    if args.stratify:
        sampled = space.sample_stratified(args.stratify, args.count, seed=args.seed, with_ranks=True)
    else:
        sampled = space.sample(args.count, replace=args.replace, seed=args.seed, with_ranks=True)
    for rank, record in sampled:
        print(json.dumps({"rank": rank, "record": record}, ensure_ascii=False, default=str))
    return 0


def command_partition(args: argparse.Namespace) -> int:
    space = _space(args.schema)
    partition = space.partition(args.worker, args.workers)
    print(_json(partition.to_dict()))
    return 0


def _rows(space: Space, start: int, stop: int) -> Iterable[dict[str, Any]]:
    for rank in range(start, stop):
        yield {"rank": rank, **space.unrank(rank)}


def command_export(args: argparse.Namespace) -> int:
    space = _space(args.schema)
    start = args.start
    stop = space.count if args.stop is None else args.stop
    if args.limit is not None:
        stop = min(stop, start + args.limit)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    rows = _rows(space, start, stop)
    if args.format == "jsonl":
        with output.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    else:
        first = next(iter(rows), None)
        with output.open("w", newline="", encoding="utf-8") as handle:
            if first is not None:
                writer = csv.DictWriter(handle, fieldnames=list(first))
                writer.writeheader()
                writer.writerow(first)
                for row in _rows(space, start + 1, stop):
                    writer.writerow(row)
    print(_json({"output": str(output), "start": start, "stop": stop, "count": stop - start}))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="finspace",
        description="Compile and operate exact finite financial scenario spaces.",
    )
    parser.add_argument("--version", action="version", version="finspace 0.1.0")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect = subparsers.add_parser("inspect", help="show domain size, hashes, and fields")
    inspect.add_argument("schema")
    inspect.set_defaults(function=command_inspect)

    rank = subparsers.add_parser("rank", help="rank a JSON record")
    rank.add_argument("schema")
    rank.add_argument("record", help="JSON string or path to a JSON file")
    rank.set_defaults(function=command_rank)

    unrank = subparsers.add_parser("unrank", help="decode one integer rank")
    unrank.add_argument("schema")
    unrank.add_argument("rank", type=int)
    unrank.set_defaults(function=command_unrank)

    validate = subparsers.add_parser("validate", help="validate and rank a record")
    validate.add_argument("schema")
    validate.add_argument("record")
    validate.set_defaults(function=command_validate)

    sample = subparsers.add_parser("sample", help="sample valid records")
    sample.add_argument("schema")
    sample.add_argument("-n", "--count", type=int, default=1)
    sample.add_argument("--seed", default=None)
    sample.add_argument("--replace", action="store_true")
    sample.add_argument("--stratify", help="balance samples across an unconditional field")
    sample.set_defaults(function=command_sample)

    partition = subparsers.add_parser("partition", help="show one deterministic worker interval")
    partition.add_argument("schema")
    partition.add_argument("--workers", type=int, required=True)
    partition.add_argument("--worker", type=int, required=True)
    partition.set_defaults(function=command_partition)

    export = subparsers.add_parser("export", help="export an interval to JSONL or CSV")
    export.add_argument("schema")
    export.add_argument("output")
    export.add_argument("--format", choices=("jsonl", "csv"), default="jsonl")
    export.add_argument("--start", type=int, default=0)
    export.add_argument("--stop", type=int)
    export.add_argument("--limit", type=int)
    export.set_defaults(function=command_export)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.function(args))
    except Exception as error:
        parser.exit(2, f"finspace: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
