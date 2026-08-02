from __future__ import annotations

import argparse
import json
import random
from typing import Sequence

from .core import SchemaError, load_schema


def _tokens(text: str) -> list[str | int]:
    value = json.loads(text)
    if not isinstance(value, list):
        raise argparse.ArgumentTypeError("value must be a JSON array")
    if any(not isinstance(item, (str, int)) or isinstance(item, bool) for item in value):
        raise argparse.ArgumentTypeError("tokens must be strings or integers")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pdrs")
    sub = parser.add_subparsers(dest="command", required=True)

    for command in ("count", "describe"):
        item = sub.add_parser(command)
        item.add_argument("schema")

    rank = sub.add_parser("rank")
    rank.add_argument("schema")
    rank.add_argument("value", type=_tokens)

    unrank = sub.add_parser("unrank")
    unrank.add_argument("schema")
    unrank.add_argument("index", type=int)

    sample = sub.add_parser("sample")
    sample.add_argument("schema")
    sample.add_argument("--number", type=int, default=1)
    sample.add_argument("--seed", type=int)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        schema = load_schema(args.schema)
        if args.command == "count":
            print(schema.count)
        elif args.command == "describe":
            print(json.dumps(schema.describe(), indent=2, sort_keys=True))
        elif args.command == "rank":
            print(schema.rank(args.value))
        elif args.command == "unrank":
            print(json.dumps(schema.unrank(args.index)))
        elif args.command == "sample":
            if args.number < 1:
                raise SchemaError("sample number must be positive")
            rng = random.Random(args.seed) if args.seed is not None else None
            values = [schema.sample(rng) for _ in range(args.number)]
            print(json.dumps(values[0] if args.number == 1 else values))
        return 0
    except (OSError, json.JSONDecodeError, SchemaError) as exc:
        parser = build_parser()
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
