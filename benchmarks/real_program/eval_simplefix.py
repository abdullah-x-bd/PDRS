from __future__ import annotations

from collections import Counter
import importlib
import json
from pathlib import Path
import random
import re
import time
from typing import Any, Sequence

import coverage

from pdrs import CompiledSchema

from .common import (
    FAILURES,
    PROCESSED,
    RAW,
    Failure,
    distinct_rank_values,
    generation_metrics,
    local_uniform_values,
    replacement_rank_values,
    timed_generate,
    worker_overlap,
    write_csv,
    write_json,
)
from .schemas import simplefix_schema

SOH = b"\x01"
SYMBOLS = ["AAPL", "MSFT", "GOOG", "AMZN", "META", "NVDA", "TSLA", "JPM", "BAC", "EUR/USD", "USD/INR", "XAU/USD"]
TIFS = ["0", "1", "3", "4", "6"]


def _decode(value: Sequence[str | int], rank: int) -> dict[str, Any]:
    tokens = list(value)
    message_type = str(tokens[0])
    cursor = 1
    result: dict[str, Any] = {"message_type": message_type, "rank": rank}
    if message_type == "D":
        result["side"] = str(tokens[cursor]); cursor += 1
        result["order_type"] = str(tokens[cursor]); cursor += 1
        result["symbol"] = SYMBOLS[int(tokens[cursor])]; cursor += 1
        result["quantity"] = (int(tokens[cursor]) + 1) * 100; cursor += 1
        if result["order_type"] in {"2", "4"}:
            result["price"] = 50.0 + int(tokens[cursor]) * 2.5; cursor += 1
        if result["order_type"] in {"3", "4"}:
            result["stop_price"] = 45.0 + int(tokens[cursor]) * 2.5; cursor += 1
        result["time_in_force"] = TIFS[int(tokens[cursor])]; cursor += 1
    elif message_type == "F":
        result["symbol"] = SYMBOLS[int(tokens[cursor])]; cursor += 1
        result["side"] = str(tokens[cursor]); cursor += 1
        result["orig_order_id"] = f"ORIG{int(tokens[cursor]):06d}"; cursor += 1
    elif message_type == "G":
        result["side"] = str(tokens[cursor]); cursor += 1
        result["order_type"] = str(tokens[cursor]); cursor += 1
        result["symbol"] = SYMBOLS[int(tokens[cursor])]; cursor += 1
        result["quantity"] = (int(tokens[cursor]) + 1) * 100; cursor += 1
        if result["order_type"] in {"2", "4"}:
            result["price"] = 50.0 + int(tokens[cursor]) * 2.5; cursor += 1
        if result["order_type"] in {"3", "4"}:
            result["stop_price"] = 45.0 + int(tokens[cursor]) * 2.5; cursor += 1
        result["orig_order_id"] = f"ORIG{int(tokens[cursor]):06d}"; cursor += 1
        result["time_in_force"] = TIFS[int(tokens[cursor])]; cursor += 1
    elif message_type == "V":
        result["subscription"] = str(tokens[cursor]); cursor += 1
        result["market_depth"] = int(tokens[cursor]) + 1; cursor += 1
        result["entry_set"] = str(tokens[cursor]); cursor += 1
        result["symbol"] = SYMBOLS[int(tokens[cursor])]; cursor += 1
    else:
        raise AssertionError(message_type)
    result["fragmentation"] = int(tokens[cursor]); cursor += 1
    if cursor != len(tokens):
        raise AssertionError(f"unconsumed SimpleFIX tokens: {tokens[cursor:]}")
    return result


def _append_header(message: Any, message_type: str, rank: int) -> None:
    message.append_pair(8, "FIX.4.4")
    message.append_pair(35, message_type)
    message.append_pair(34, rank % 999999 + 1, header=True)
    message.append_pair(49, "PDRS_SENDER", header=True)
    message.append_pair(52, "20260802-13:30:00.000", header=True)
    message.append_pair(56, "PDRS_TARGET", header=True)


def _build_message(simplefix: Any, case: dict[str, Any]) -> tuple[bytes, dict[int, str]]:
    message = simplefix.FixMessage()
    rank = int(case["rank"])
    message_type = str(case["message_type"])
    _append_header(message, message_type, rank)
    expected: dict[int, str] = {35: message_type, 49: "PDRS_SENDER", 56: "PDRS_TARGET"}
    if message_type == "D":
        pairs = [
            (11, f"PDRS{rank:012d}"), (21, "1"), (55, case["symbol"]),
            (54, case["side"]), (60, "20260802-13:30:00.000"),
            (38, str(case["quantity"])), (40, case["order_type"]),
            (59, case["time_in_force"]),
        ]
        if "price" in case:
            pairs.append((44, f"{case['price']:.2f}"))
        if "stop_price" in case:
            pairs.append((99, f"{case['stop_price']:.2f}"))
    elif message_type == "F":
        pairs = [
            (41, case["orig_order_id"]), (11, f"CXL{rank:012d}"),
            (55, case["symbol"]), (54, case["side"]),
            (60, "20260802-13:30:00.000"),
        ]
    elif message_type == "G":
        pairs = [
            (41, case["orig_order_id"]), (11, f"RPL{rank:012d}"),
            (21, "1"), (55, case["symbol"]), (54, case["side"]),
            (60, "20260802-13:30:00.000"), (38, str(case["quantity"])),
            (40, case["order_type"]), (59, case["time_in_force"]),
        ]
        if "price" in case:
            pairs.append((44, f"{case['price']:.2f}"))
        if "stop_price" in case:
            pairs.append((99, f"{case['stop_price']:.2f}"))
    else:
        entry_types = ["0"] if case["entry_set"] == "BID" else ["1"] if case["entry_set"] == "OFFER" else ["0", "1"]
        pairs = [
            (262, f"MD{rank:012d}"), (263, case["subscription"]),
            (264, str(case["market_depth"])), (267, str(len(entry_types))),
        ]
        for entry in entry_types:
            message.append_pair(269, entry)
        pairs.extend([(146, "1"), (55, case["symbol"])])
    for tag, value in pairs:
        message.append_pair(tag, value)
        expected[int(tag)] = str(value)
    return message.encode(), expected


def _chunks(encoded: bytes, pattern: int, rank: int) -> list[bytes]:
    if pattern == 0:
        return [encoded]
    if pattern == 1:
        return [encoded[index:index + 1] for index in range(len(encoded))]
    if pattern == 2:
        middle = len(encoded) // 2
        return [encoded[:middle], encoded[middle:]]
    if pattern == 3:
        return [encoded[index:index + 7] for index in range(0, len(encoded), 7)]
    if pattern == 4:
        body_start = encoded.find(SOH, encoded.find(b"9=")) + 1
        checksum_start = encoded.rfind(b"10=")
        return [encoded[:body_start], encoded[body_start:checksum_start], encoded[checksum_start:]]
    rng = random.Random(rank)
    output: list[bytes] = []
    cursor = 0
    while cursor < len(encoded):
        width = rng.randint(1, 17)
        output.append(encoded[cursor:cursor + width])
        cursor += width
    return output


def _text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("ascii")
    return str(value)


def _integrity(encoded: bytes) -> tuple[bool, bool]:
    match = re.search(br"\x019=(\d+)\x01", encoded)
    if match is None:
        return False, False
    body_start = match.end()
    checksum_start = encoded.rfind(b"10=")
    body_ok = int(match.group(1)) == checksum_start - body_start
    checksum_match = re.search(br"10=(\d{3})\x01$", encoded)
    checksum_ok = bool(checksum_match) and int(checksum_match.group(1)) == sum(encoded[:checksum_start]) % 256
    return body_ok, checksum_ok


def _parse(simplefix: Any, encoded: bytes, pattern: int, rank: int) -> Any:
    parser = simplefix.FixParser()
    found = None
    for chunk in _chunks(encoded, pattern, rank):
        parser.append_buffer(chunk)
        candidate = parser.get_message()
        if candidate is not None:
            if found is not None:
                raise AssertionError("multiple messages parsed from one encoded input")
            found = candidate
    if found is None:
        found = parser.get_message()
    return found


def _exercise(simplefix: Any, schema: CompiledSchema, values: Sequence[Sequence[str | int]]) -> tuple[dict[str, Any], list[Failure]]:
    failures: list[Failure] = []
    encoded_bytes = 0
    message_types: Counter[str] = Counter()
    started = time.perf_counter()
    for value in values:
        rank = schema.rank(value)
        case = _decode(value, rank)
        message_types[case["message_type"]] += 1
        try:
            encoded, expected = _build_message(simplefix, case)
            encoded_bytes += len(encoded)
            body_ok, checksum_ok = _integrity(encoded)
            if not body_ok:
                failures.append(Failure("simplefix", rank, "body_length", "encoded BodyLength mismatch", value))
            if not checksum_ok:
                failures.append(Failure("simplefix", rank, "checksum", "encoded CheckSum mismatch", value))
            parsed = _parse(simplefix, encoded, case["fragmentation"], rank)
            if parsed is None:
                failures.append(Failure("simplefix", rank, "parse", "valid encoded message was not parsed", value))
                continue
            for tag, expected_value in expected.items():
                actual = _text(parsed.get(tag))
                if actual != expected_value:
                    failures.append(Failure("simplefix", rank, f"tag_{tag}", f"expected {expected_value!r}, got {actual!r}", value))
        except Exception as error:  # recorded with rank and exact PDRS value
            failures.append(Failure("simplefix", rank, "exception", f"{type(error).__name__}: {error}", value))
    elapsed = time.perf_counter() - started
    return {
        "executed": len(values),
        "seconds": elapsed,
        "cases_per_second": len(values) / elapsed if elapsed else float("inf"),
        "encoded_bytes": encoded_bytes,
        "oracle_failures": len(failures),
        "message_type_counts": dict(message_types),
    }, failures


def _coverage_run(method: str, values: list[list[str | int]], schema: CompiledSchema) -> tuple[dict[str, Any], list[Failure]]:
    report_path = PROCESSED / f"simplefix_coverage_{method}.json"
    data_path = PROCESSED / f".coverage.simplefix.{method}"
    cov = coverage.Coverage(branch=True, source=["simplefix"], data_file=str(data_path))
    cov.erase()
    cov.start()
    simplefix = importlib.import_module("simplefix")
    execution, failures = _exercise(simplefix, schema, values)
    cov.stop()
    cov.save()
    cov.json_report(outfile=str(report_path))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    totals = report["totals"]
    execution.update({
        "method": method,
        "coverage_percent": totals["percent_covered"],
        "covered_lines": totals["covered_lines"],
        "num_statements": totals["num_statements"],
        "covered_branches": totals["covered_branches"],
        "num_branches": totals["num_branches"],
    })
    return execution, failures


def _mutation_outcomes(simplefix: Any, schema: CompiledSchema, budget: int, seed: int) -> list[dict[str, Any]]:
    values = distinct_rank_values(schema, budget, seed)
    rows: list[dict[str, Any]] = []
    for value in values:
        rank = schema.rank(value)
        case = _decode(value, rank)
        encoded, _ = _build_message(simplefix, case)
        checksum_start = encoded.rfind(b"10=")
        mutations = {
            "bad_checksum": encoded[:checksum_start] + b"10=999\x01",
            "truncated": encoded[:max(1, len(encoded) - 8)],
            "missing_begin": encoded[encoded.find(SOH) + 1:],
            "empty_sender": encoded.replace(b"49=PDRS_SENDER\x01", b"49=\x01", 1),
        }
        body_match = re.search(br"\x019=(\d+)\x01", encoded)
        if body_match:
            old = body_match.group(1)
            replacement = str(int(old) + 1).encode("ascii")
            mutations["bad_body_length"] = encoded[:body_match.start(1)] + replacement + encoded[body_match.end(1):]
        for mutation, payload in mutations.items():
            outcome = "message"
            detail = ""
            try:
                parser = simplefix.FixParser()
                parser.append_buffer(payload)
                parsed = parser.get_message()
                if parsed is None:
                    outcome = "none"
            except Exception as error:
                outcome = "exception"
                detail = type(error).__name__
            rows.append({"rank": rank, "mutation": mutation, "outcome": outcome, "detail": detail})
    return rows


def run(budget: int = 4000, seed: int = 20260802) -> dict[str, Any]:
    schema = CompiledSchema(simplefix_schema())
    methods = {
        "pdrs_without_replacement": lambda: distinct_rank_values(schema, budget, seed),
        "pdrs_with_replacement": lambda: replacement_rank_values(schema, budget, seed),
        "local_uniform_grammar": lambda: local_uniform_values(schema, budget, seed),
    }
    rows: list[dict[str, Any]] = []
    all_failures: list[Failure] = []
    for name, generator in methods.items():
        values, generation_seconds = timed_generate(generator)
        generation = generation_metrics(values, generation_seconds)
        execution, failures = _coverage_run(name, values, schema)
        all_failures.extend(failures)
        rows.append({"evaluation": "simplefix", **generation, **execution})
    simplefix = importlib.import_module("simplefix")
    mutation_rows = _mutation_outcomes(simplefix, schema, min(400, budget), seed + 77)
    write_csv(RAW / "simplefix_methods.csv", rows)
    write_csv(RAW / "simplefix_mutations.csv", mutation_rows)
    write_json(FAILURES / "simplefix_failures.json", [failure.as_dict() for failure in all_failures])
    overlap = worker_overlap(schema, workers=8, per_worker=500, seed=seed)
    mutation_summary: dict[str, dict[str, int]] = {}
    for row in mutation_rows:
        mutation_summary.setdefault(row["mutation"], {})[row["outcome"]] = mutation_summary.setdefault(row["mutation"], {}).get(row["outcome"], 0) + 1
    summary = {
        "package": "simplefix",
        "package_version": getattr(simplefix, "__version__", "1.0.17"),
        "schema_count": schema.count,
        "schema_hash": schema.canonical_hash,
        "budget_per_method": budget,
        "methods": rows,
        "valid_oracle_failures": len(all_failures),
        "mutations": mutation_summary,
        **overlap,
    }
    write_json(PROCESSED / "simplefix_summary.json", summary)
    return summary
