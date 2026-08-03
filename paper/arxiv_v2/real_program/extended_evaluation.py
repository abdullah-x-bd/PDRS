from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
import math
from pathlib import Path
import re
import sys
import time
from typing import Any


def repository_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "benchmarks" / "real_program").exists() and (parent / "pyproject.toml").exists():
            return parent
    raise RuntimeError("could not locate repository root")


REPO = repository_root()
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))

from pdrs import CompiledSchema
from benchmarks.real_program.eval_quantlib import _black_scholes, _quantlib_price
from benchmarks.real_program.eval_simplefix import _build_message, _decode as decode_fix, _parse
from benchmarks.real_program.eval_iso20022 import _build as build_iso, _decode as decode_iso, _validators
from benchmarks.real_program.schemas import iso20022_schema, simplefix_schema

RESULTS = REPO / "results" / "real_program_v2"
RESULTS.mkdir(parents=True, exist_ok=True)


def write_json(name: str, value: Any) -> None:
    (RESULTS / name).write_text(json.dumps(value, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def quantlib_extended() -> dict[str, Any]:
    import QuantLib as ql

    cases: list[dict[str, Any]] = []
    regimes = [
        ("near_zero_maturity", 100.0, 100.0, 1, 0.2, 0.01, 0.0),
        ("near_zero_volatility", 100.0, 100.0, 365, 1e-6, 0.01, 0.0),
        ("negative_rate", 100.0, 100.0, 365, 0.2, -0.02, 0.0),
        ("deep_itm", 200.0, 50.0, 365, 0.3, 0.02, 0.01),
        ("deep_otm", 50.0, 200.0, 365, 0.3, 0.02, 0.01),
        ("long_maturity", 100.0, 100.0, 3650, 0.8, 0.08, 0.07),
    ]
    rank = 0
    for name, spot, strike, days, volatility, rate, dividend in regimes:
        for option_type in ("call", "put"):
            cases.append({
                "rank": rank,
                "regime": name,
                "option_type": option_type,
                "currency": "USD",
                "rate": rate,
                "spot": spot,
                "strike": strike,
                "maturity_class": "boundary",
                "maturity_days": days,
                "volatility": volatility,
                "dividend": dividend,
                "engine_profile": "cross_engine",
            })
            rank += 1

    rows = []
    failures = []
    for case in cases:
        started = time.perf_counter()
        try:
            analytic = _quantlib_price(ql, case, "analytic")
            formula = _black_scholes(case)
            error = abs(analytic - formula)
            bump = max(1e-4, abs(case["spot"]) * 1e-4)
            up = _quantlib_price(ql, dict(case, spot=case["spot"] + bump), "analytic")
            down = _quantlib_price(ql, dict(case, spot=max(1e-10, case["spot"] - bump)), "analytic")
            finite_difference_delta = (up - down) / (2.0 * bump)
            binomial = _quantlib_price(ql, case, "binomial")
            finite_difference = _quantlib_price(ql, case, "finite_difference")
            finite = all(math.isfinite(value) for value in (analytic, formula, finite_difference_delta, binomial, finite_difference))
            if not finite or error > max(1e-8, abs(formula) * 1e-8):
                failures.append({"regime": case["regime"], "option_type": case["option_type"], "analytic_error": error, "finite": finite})
            rows.append({
                "regime": case["regime"],
                "option_type": case["option_type"],
                "analytic": analytic,
                "independent_formula": formula,
                "analytic_error": error,
                "finite_difference_delta": finite_difference_delta,
                "binomial_error": abs(binomial - analytic),
                "finite_difference_engine_error": abs(finite_difference - analytic),
                "finite": finite,
                "elapsed_ms": (time.perf_counter() - started) * 1000.0,
            })
        except Exception as error:
            failures.append({"regime": case["regime"], "option_type": case["option_type"], "exception": f"{type(error).__name__}: {error}"})

    result = {
        "status": "complete",
        "package": "QuantLib",
        "version": getattr(ql, "__version__", "unknown"),
        "boundary_cases": len(cases),
        "failures": failures,
        "rows": rows,
        "scope": "Boundary and differential-oracle extension for European options; no historical or previously unknown defect claim.",
    }
    write_json("quantlib_extended.json", result)
    return result


def first_rank_by_fix_type(schema: CompiledSchema, message_type: str) -> int:
    return int(schema._choice_lookup[schema.root][message_type][1])


def mutate_fix(encoded: bytes) -> dict[str, bytes]:
    output: dict[str, bytes] = {}
    output["bad_checksum_digits"] = re.sub(br"10=\d{3}\x01$", b"10=999\x01", encoded)
    output["missing_final_delimiter"] = encoded[:-1]
    output["nonnumeric_body_length"] = re.sub(br"\x019=\d+\x01", b"\x019=ABC\x01", encoded, count=1)
    output["unknown_message_type"] = encoded.replace(b"\x0135=", b"\x0135=Z", 1).replace(b"Z" + encoded.split(b"\x0135=", 1)[1].split(b"\x01", 1)[0] + b"\x01", b"Z\x01", 1)
    sender = re.search(br"\x0149=[^\x01]+\x01", encoded)
    output["duplicate_sender"] = encoded if sender is None else encoded.replace(sender.group(0), sender.group(0) + sender.group(0), 1)
    checksum = encoded.rfind(b"10=")
    output["header_after_body"] = encoded if checksum < 0 else encoded[:checksum] + b"49=LATE_SENDER\x01" + encoded[checksum:]
    return output


def simplefix_extended() -> dict[str, Any]:
    import simplefix

    schema = CompiledSchema(simplefix_schema())
    valid_rows = []
    mutation_rows = []
    for message_type in ("D", "F", "G", "V"):
        rank = first_rank_by_fix_type(schema, message_type)
        value = schema.unrank(rank)
        case = decode_fix(value, rank)
        encoded, _ = _build_message(simplefix, case)
        parsed = _parse(simplefix, encoded, int(case["fragmentation"]), rank)
        valid_rows.append({"message_type": message_type, "rank": rank, "bytes": len(encoded), "parsed": parsed is not None})
        for mutation, payload in mutate_fix(encoded).items():
            try:
                candidate = _parse(simplefix, payload, 0, rank)
                outcome = "message" if candidate is not None else "none"
                detail = ""
            except Exception as error:
                outcome = "exception"
                detail = f"{type(error).__name__}: {error}"
            mutation_rows.append({"message_type": message_type, "rank": rank, "mutation": mutation, "outcome": outcome, "detail": detail})

    result = {
        "status": "complete",
        "package": "simplefix",
        "version": getattr(simplefix, "__version__", "1.0.17"),
        "valid_profiles": valid_rows,
        "mutation_outcomes": mutation_rows,
        "outcome_counts": dict(Counter(row["outcome"] for row in mutation_rows)),
        "scope": "Parser-behaviour characterization across four FIX message families. A parsed malformed message is not automatically classified as a library defect.",
    }
    write_json("simplefix_extended.json", result)
    return result


def first_rank_by_iso_type(schema: CompiledSchema, message: str) -> int:
    return int(schema._choice_lookup[schema.root][message][1])


def mutate_iso(encoded: bytes) -> dict[str, bytes]:
    from lxml import etree

    root = etree.fromstring(encoded)
    output: dict[str, bytes] = {}

    long_identifier = deepcopy(root)
    identifier = long_identifier.xpath("//*[local-name()='MsgId']")[0]
    identifier.text = "X" * 80
    output["identifier_length"] = etree.tostring(long_identifier, xml_declaration=True, encoding="UTF-8")

    fraction = deepcopy(root)
    amount = fraction.xpath("//*[@Ccy]")[0]
    amount.text = "1.001"
    output["fraction_digits"] = etree.tostring(fraction, xml_declaration=True, encoding="UTF-8")

    invalid_date = deepcopy(root)
    dates = invalid_date.xpath("//*[local-name()='Dt' or local-name()='IntrBkSttlmDt']")
    if dates:
        dates[0].text = "2026-02-31"
    output["invalid_date"] = etree.tostring(invalid_date, xml_declaration=True, encoding="UTF-8")

    wrong_order = deepcopy(root)
    candidates = wrong_order.xpath("//*[count(*) > 2]")
    container = candidates[-1] if candidates else wrong_order
    if len(container) > 1:
        last = container[-1]
        container.remove(last)
        container.insert(0, last)
    output["element_order"] = etree.tostring(wrong_order, xml_declaration=True, encoding="UTF-8")

    unexpected = deepcopy(root)
    namespace = etree.QName(unexpected).namespace or ""
    etree.SubElement(unexpected, f"{{{namespace}}}Unexpected").text = "x"
    output["unexpected_element"] = etree.tostring(unexpected, xml_declaration=True, encoding="UTF-8")

    invalid_enum = deepcopy(root)
    enums = invalid_enum.xpath("//*[local-name()='PmtMtd' or local-name()='ChrgBr']")
    if enums:
        enums[0].text = "XXXX"
    output["invalid_enumeration"] = etree.tostring(invalid_enum, xml_declaration=True, encoding="UTF-8")
    return output


def iso_extended(xsd_dir: Path) -> dict[str, Any]:
    from lxml import etree
    import xmlschema as xmlschema_package

    schema = CompiledSchema(iso20022_schema())
    xsd_paths = {
        "pain.001.001.13": xsd_dir / "pain.001.001.13.xsd",
        "pacs.008.001.14": xsd_dir / "pacs.008.001.14.xsd",
    }
    validators = {name: _validators(path) for name, path in xsd_paths.items()}
    valid_rows = []
    mutation_rows = []
    for message in xsd_paths:
        rank = first_rank_by_iso_type(schema, message)
        value = schema.unrank(rank)
        case = decode_iso(value, rank)
        encoded = build_iso(case)
        lxml_schema, independent = validators[message]
        valid_rows.append({
            "message": message,
            "rank": rank,
            "lxml_valid": lxml_schema.validate(etree.fromstring(encoded)),
            "xmlschema_valid": independent.is_valid(encoded),
            "bytes": len(encoded),
        })
        for mutation, payload in mutate_iso(encoded).items():
            lxml_valid = lxml_schema.validate(etree.fromstring(payload))
            independent_valid = independent.is_valid(payload)
            mutation_rows.append({
                "message": message,
                "rank": rank,
                "mutation": mutation,
                "lxml_valid": lxml_valid,
                "xmlschema_valid": independent_valid,
                "disagreement": lxml_valid != independent_valid,
            })

    result = {
        "status": "complete",
        "packages": {
            "lxml": ".".join(str(item) for item in etree.LXML_VERSION),
            "xmlschema": xmlschema_package.__version__,
        },
        "valid_profiles": valid_rows,
        "mutation_outcomes": mutation_rows,
        "validator_disagreements": sum(row["disagreement"] for row in mutation_rows),
        "rejected_by_both": sum(not row["lxml_valid"] and not row["xmlschema_valid"] for row in mutation_rows),
        "scope": "XSD facet, order, cardinality, and enumeration smoke tests over two bounded message profiles; shared schemas mean the validators are implementation-diverse, not semantically independent oracles.",
    }
    write_json("iso20022_extended.json", result)
    return result


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: extended_evaluation.py XSD_DIRECTORY")
    xsd_dir = Path(sys.argv[1])
    summary = {
        "quantlib": quantlib_extended(),
        "simplefix": simplefix_extended(),
        "iso20022": iso_extended(xsd_dir),
        "claim_boundary": "This extension strengthens boundary and mutation coverage. It does not claim a previously unknown defect unless a failure receives independent upstream confirmation.",
    }
    write_json("summary.json", summary)
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
