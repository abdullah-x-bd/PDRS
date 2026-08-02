from __future__ import annotations

from collections import Counter
from copy import deepcopy
from decimal import Decimal
import math
from pathlib import Path
import time
from typing import Any, Sequence

from lxml import etree
import xmlschema as xmlschema_package

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
from .schemas import iso20022_schema

PAIN_NS = "urn:iso:std:iso:20022:tech:xsd:pain.001.001.13"
PACS_NS = "urn:iso:std:iso:20022:tech:xsd:pacs.008.001.14"
AMOUNTS = [Decimal("0.01"), Decimal("1.00"), Decimal("5.00"), Decimal("10.00"), Decimal("25.00"), Decimal("50.00"), Decimal("100.00"), Decimal("250.00"), Decimal("500.00"), Decimal("1000.00"), Decimal("2500.00"), Decimal("5000.00"), Decimal("10000.00"), Decimal("25000.00"), Decimal("50000.00"), Decimal("100000.00"), Decimal("250000.00"), Decimal("500000.00"), Decimal("1000000.00"), Decimal("2500000.00"), Decimal("5000000.00"), Decimal("10000000.00"), Decimal("25000000.00"), Decimal("50000000.00"), Decimal("99999999.99")]
NAMES = ["Aster Labs", "Bharat Exports", "Cedar Finance", "Delta Works", "Eastbridge Ltd", "Futura Systems", "Global Textiles", "Horizon Foods"]
IBANS = ["DE89370400440532013000", "GB29NWBK60161331926819", "FR1420041010050500013M02606", "NL91ABNA0417164300", "ES9121000418450200051332", "IT60X0542811101000000123456", "BE68539007547034", "LU280019400644750000"]
BICS = ["DEUTDEFF", "NWBKGB2L", "BNPAFRPP", "ABNANL2A", "CAIXESBB", "BCITITMM", "KREDBEBB", "BCEELULL"]
REMITTANCES = ["INV-2026-0001", "SALARY-AUG", "SUPPLIER-SETTLEMENT", "TAX-PAYMENT", "SUBSCRIPTION", "REFUND", "INTERCOMPANY", "INSURANCE", "RENT", "UTILITIES", "DIVIDEND", "TRADE-001", "PROJECT-A", "DONATION", "ROYALTY", "CONSULTING"]


def _decode(value: Sequence[str | int], rank: int) -> dict[str, Any]:
    tokens = list(value)
    message = str(tokens[0])
    currency = str(tokens[1])
    amount = AMOUNTS[int(tokens[2])]
    debtor_index = int(tokens[3])
    creditor_index = int(tokens[4])
    day = int(tokens[5])
    if message.startswith("pain"):
        return {
            "rank": rank, "message": message, "currency": currency, "amount": amount,
            "debtor_index": debtor_index, "creditor_index": creditor_index,
            "day": day, "batch_booking": str(tokens[6]), "remittance_index": int(tokens[7]),
        }
    return {
        "rank": rank, "message": message, "currency": currency, "amount": amount,
        "debtor_index": debtor_index, "creditor_index": creditor_index,
        "day": day, "charge_bearer": str(tokens[6]), "priority": str(tokens[7]),
    }


def _sub(parent: etree._Element, namespace: str, name: str, text: str | None = None, **attributes: str) -> etree._Element:
    child = etree.SubElement(parent, f"{{{namespace}}}{name}", **attributes)
    if text is not None:
        child.text = text
    return child


def _party(parent: etree._Element, namespace: str, tag: str, name: str) -> None:
    party = _sub(parent, namespace, tag)
    _sub(party, namespace, "Nm", name)


def _account(parent: etree._Element, namespace: str, tag: str, iban: str) -> None:
    account = _sub(parent, namespace, tag)
    identifier = _sub(account, namespace, "Id")
    _sub(identifier, namespace, "IBAN", iban)


def _agent(parent: etree._Element, namespace: str, tag: str, bic: str) -> None:
    agent = _sub(parent, namespace, tag)
    institution = _sub(agent, namespace, "FinInstnId")
    _sub(institution, namespace, "BICFI", bic)


def _pain(case: dict[str, Any]) -> bytes:
    ns = PAIN_NS
    root = etree.Element(f"{{{ns}}}Document", nsmap={None: ns})
    initiation = _sub(root, ns, "CstmrCdtTrfInitn")
    header = _sub(initiation, ns, "GrpHdr")
    _sub(header, ns, "MsgId", f"PDRS-PAIN-{case['rank']:016d}")
    _sub(header, ns, "CreDtTm", "2026-08-02T13:30:00Z")
    _sub(header, ns, "NbOfTxs", "1")
    _sub(header, ns, "CtrlSum", f"{case['amount']:.2f}")
    _party(header, ns, "InitgPty", NAMES[case["debtor_index"]])

    payment = _sub(initiation, ns, "PmtInf")
    _sub(payment, ns, "PmtInfId", f"PMT-{case['rank']:016d}")
    _sub(payment, ns, "PmtMtd", "TRF")
    _sub(payment, ns, "BtchBookg", case["batch_booking"])
    _sub(payment, ns, "NbOfTxs", "1")
    _sub(payment, ns, "CtrlSum", f"{case['amount']:.2f}")
    requested = _sub(payment, ns, "ReqdExctnDt")
    _sub(requested, ns, "Dt", f"2026-08-{case['day']:02d}")
    _party(payment, ns, "Dbtr", NAMES[case["debtor_index"]])
    _account(payment, ns, "DbtrAcct", IBANS[case["debtor_index"]])
    _agent(payment, ns, "DbtrAgt", BICS[case["debtor_index"]])

    transaction = _sub(payment, ns, "CdtTrfTxInf")
    identification = _sub(transaction, ns, "PmtId")
    _sub(identification, ns, "InstrId", f"INSTR-{case['rank']:016d}")
    _sub(identification, ns, "EndToEndId", f"E2E-{case['rank']:016d}")
    amount = _sub(transaction, ns, "Amt")
    _sub(amount, ns, "InstdAmt", f"{case['amount']:.2f}", Ccy=case["currency"])
    _agent(transaction, ns, "CdtrAgt", BICS[case["creditor_index"]])
    _party(transaction, ns, "Cdtr", NAMES[case["creditor_index"]])
    _account(transaction, ns, "CdtrAcct", IBANS[case["creditor_index"]])
    remittance = _sub(transaction, ns, "RmtInf")
    _sub(remittance, ns, "Ustrd", REMITTANCES[case["remittance_index"]])
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8")


def _pacs(case: dict[str, Any]) -> bytes:
    ns = PACS_NS
    root = etree.Element(f"{{{ns}}}Document", nsmap={None: ns})
    transfer = _sub(root, ns, "FIToFICstmrCdtTrf")
    header = _sub(transfer, ns, "GrpHdr")
    _sub(header, ns, "MsgId", f"PDRS-PACS-{case['rank']:016d}")
    _sub(header, ns, "CreDtTm", "2026-08-02T13:30:00Z")
    _sub(header, ns, "NbOfTxs", "1")
    settlement = _sub(header, ns, "SttlmInf")
    _sub(settlement, ns, "SttlmMtd", "CLRG")

    transaction = _sub(transfer, ns, "CdtTrfTxInf")
    identification = _sub(transaction, ns, "PmtId")
    _sub(identification, ns, "InstrId", f"INSTR-{case['rank']:016d}")
    _sub(identification, ns, "EndToEndId", f"E2E-{case['rank']:016d}")
    _sub(identification, ns, "TxId", f"TX-{case['rank']:016d}")
    _sub(transaction, ns, "IntrBkSttlmAmt", f"{case['amount']:.2f}", Ccy=case["currency"])
    _sub(transaction, ns, "IntrBkSttlmDt", f"2026-08-{case['day']:02d}")
    _sub(transaction, ns, "SttlmPrty", case["priority"])
    _sub(transaction, ns, "ChrgBr", case["charge_bearer"])
    _agent(transaction, ns, "InstgAgt", BICS[case["debtor_index"]])
    _agent(transaction, ns, "InstdAgt", BICS[case["creditor_index"]])
    _party(transaction, ns, "Dbtr", NAMES[case["debtor_index"]])
    _account(transaction, ns, "DbtrAcct", IBANS[case["debtor_index"]])
    _agent(transaction, ns, "DbtrAgt", BICS[case["debtor_index"]])
    _agent(transaction, ns, "CdtrAgt", BICS[case["creditor_index"]])
    _party(transaction, ns, "Cdtr", NAMES[case["creditor_index"]])
    _account(transaction, ns, "CdtrAcct", IBANS[case["creditor_index"]])
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8")


def _build(case: dict[str, Any]) -> bytes:
    return _pain(case) if case["message"].startswith("pain") else _pacs(case)


def _validators(xsd_path: Path) -> tuple[etree.XMLSchema, xmlschema_package.XMLSchema]:
    lxml_schema = etree.XMLSchema(etree.parse(str(xsd_path)))
    independent = xmlschema_package.XMLSchema(str(xsd_path))
    return lxml_schema, independent


def _xpath_text(root: etree._Element, namespace: str, local_name: str) -> str | None:
    found = root.xpath(f"//*[local-name()='{local_name}']")
    return found[0].text if found else None


def _mutations(encoded: bytes) -> dict[str, bytes]:
    root = etree.fromstring(encoded)
    namespace = etree.QName(root).namespace or ""
    output: dict[str, bytes] = {}

    missing = deepcopy(root)
    msg_id = missing.xpath("//*[local-name()='MsgId']")[0]
    msg_id.getparent().remove(msg_id)
    output["missing_msg_id"] = etree.tostring(missing, xml_declaration=True, encoding="UTF-8")

    bad_currency = deepcopy(root)
    amount = bad_currency.xpath("//*[@Ccy]")[0]
    amount.set("Ccy", "EU1")
    output["invalid_currency"] = etree.tostring(bad_currency, xml_declaration=True, encoding="UTF-8")

    bad_amount = deepcopy(root)
    amount = bad_amount.xpath("//*[@Ccy]")[0]
    amount.text = "-1.00"
    output["negative_amount"] = etree.tostring(bad_amount, xml_declaration=True, encoding="UTF-8")

    duplicate = deepcopy(root)
    nb = duplicate.xpath("//*[local-name()='NbOfTxs']")[0]
    nb.addnext(deepcopy(nb))
    output["duplicate_nb_of_txs"] = etree.tostring(duplicate, xml_declaration=True, encoding="UTF-8")

    wrong_ns = encoded.replace(namespace.encode("utf-8"), b"urn:pdrs:wrong:namespace")
    output["wrong_namespace"] = wrong_ns
    return output


def run(xsd_dir: Path, budget: int = 1200, seed: int = 20260802) -> dict[str, Any]:
    schema = CompiledSchema(iso20022_schema())
    xsd_paths = {
        "pain.001.001.13": xsd_dir / "pain.001.001.13.xsd",
        "pacs.008.001.14": xsd_dir / "pacs.008.001.14.xsd",
    }
    validators = {message: _validators(path) for message, path in xsd_paths.items()}
    generation_rows: list[dict[str, Any]] = []
    methods = {
        "pdrs_without_replacement": lambda: distinct_rank_values(schema, budget, seed),
        "pdrs_with_replacement": lambda: replacement_rank_values(schema, budget, seed),
        "local_uniform_grammar": lambda: local_uniform_values(schema, budget, seed),
    }
    generated: dict[str, list[list[str | int]]] = {}
    for method, generator in methods.items():
        values, elapsed = timed_generate(generator)
        generated[method] = values
        generation_rows.append({"evaluation": "iso20022", "method": method, **generation_metrics(values, elapsed)})

    rows: list[dict[str, Any]] = []
    failures: list[Failure] = []
    message_counts: Counter[str] = Counter()
    for value in generated["pdrs_without_replacement"]:
        rank = schema.rank(value)
        case = _decode(value, rank)
        message_counts[case["message"]] += 1
        encoded = _build(case)
        lxml_schema, independent = validators[case["message"]]
        started = time.perf_counter()
        lxml_valid = lxml_schema.validate(etree.fromstring(encoded))
        xmlschema_valid = independent.is_valid(encoded)
        parse_ok = True
        detail = ""
        try:
            decoded = independent.to_dict(encoded)
            parse_ok = decoded is not None
        except Exception as error:
            parse_ok = False
            detail = f"{type(error).__name__}: {error}"
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        root = etree.fromstring(encoded)
        namespace = etree.QName(root).namespace or ""
        msg_id = _xpath_text(root, namespace, "MsgId")
        amount = _xpath_text(root, namespace, "InstdAmt") or _xpath_text(root, namespace, "IntrBkSttlmAmt")
        semantic_ok = bool(msg_id) and amount == f"{case['amount']:.2f}"
        if not lxml_valid:
            failures.append(Failure("iso20022", rank, "lxml_xsd", str(lxml_schema.error_log.last_error), value))
        if not xmlschema_valid:
            first_error = next(independent.iter_errors(encoded), None)
            failures.append(Failure("iso20022", rank, "xmlschema_xsd", str(first_error), value))
        if not parse_ok:
            failures.append(Failure("iso20022", rank, "xmlschema_decode", detail, value))
        if not semantic_ok:
            failures.append(Failure("iso20022", rank, "semantic_roundtrip", f"MsgId={msg_id!r}, amount={amount!r}", value))
        rows.append({
            "rank": rank, "message": case["message"], "bytes": len(encoded),
            "lxml_valid": lxml_valid, "xmlschema_valid": xmlschema_valid,
            "decode_ok": parse_ok, "semantic_ok": semantic_ok,
            "validation_ms": elapsed_ms,
        })

    mutation_rows: list[dict[str, Any]] = []
    for value in generated["pdrs_without_replacement"][:min(200, budget)]:
        rank = schema.rank(value)
        case = _decode(value, rank)
        lxml_schema, independent = validators[case["message"]]
        for mutation, payload in _mutations(_build(case)).items():
            lxml_valid = lxml_schema.validate(etree.fromstring(payload)) if mutation != "wrong_namespace" else lxml_schema.validate(etree.fromstring(payload))
            xmlschema_valid = independent.is_valid(payload)
            mutation_rows.append({
                "rank": rank, "message": case["message"], "mutation": mutation,
                "lxml_valid": lxml_valid, "xmlschema_valid": xmlschema_valid,
                "validators_agree": lxml_valid == xmlschema_valid,
            })

    write_csv(RAW / "iso20022_generation.csv", generation_rows)
    write_csv(RAW / "iso20022_validation.csv", rows)
    write_csv(RAW / "iso20022_mutations.csv", mutation_rows)
    write_json(FAILURES / "iso20022_failures.json", [failure.as_dict() for failure in failures])
    mutation_rejected = sum(1 for row in mutation_rows if not row["lxml_valid"] and not row["xmlschema_valid"])
    summary = {
        "packages": {"xmlschema": xmlschema_package.__version__, "lxml": etree.LXML_VERSION},
        "official_xsds": {message: str(path) for message, path in xsd_paths.items()},
        "schema_count": schema.count,
        "schema_hash": schema.canonical_hash,
        "budget": budget,
        "generation": generation_rows,
        "message_counts": dict(message_counts),
        "valid_documents": len(rows),
        "valid_document_failures": len(failures),
        "mutations": len(mutation_rows),
        "mutations_rejected_by_both": mutation_rejected,
        "mutation_rejection_rate": mutation_rejected / len(mutation_rows) if mutation_rows else 0.0,
        "validator_disagreements": sum(1 for row in mutation_rows if not row["validators_agree"]),
        **worker_overlap(schema, workers=8, per_worker=1000, seed=seed),
    }
    write_json(PROCESSED / "iso20022_summary.json", summary)
    return summary
