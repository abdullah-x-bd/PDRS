from __future__ import annotations

import json
from pathlib import Path

from pdrs.generators import calendar_schema


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"


def write(name: str, document: dict) -> None:
    (SCHEMAS / name).write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def permit_schema() -> dict:
    return {
        "name": "permit-record",
        "version": "1",
        "root": "permit_type",
        "nodes": {
            "permit_type": {
                "type": "choice",
                "field": "permit_type",
                "branches": [
                    {"value": "research", "target": "research_district"},
                    {"value": "transit", "target": "transit_port"},
                    {"value": "experimental", "target": "experimental_lab"},
                ],
            },
            "research_district": {
                "type": "range", "field": "district", "start": 0, "stop": 11,
                "target": "research_serial",
            },
            "research_serial": {
                "type": "range", "field": "serial", "start": 0, "stop": 99,
                "target": "end",
            },
            "transit_port": {
                "type": "range", "field": "port", "start": 0, "stop": 3,
                "target": "transit_serial",
            },
            "transit_serial": {
                "type": "range", "field": "serial", "start": 0, "stop": 499,
                "target": "end",
            },
            "experimental_lab": {
                "type": "range", "field": "laboratory", "start": 0, "stop": 19,
                "target": "experimental_serial",
            },
            "experimental_serial": {
                "type": "range", "field": "serial", "start": 0, "stop": 39,
                "target": "end",
            },
            "end": {"type": "terminal"},
        },
    }


def ai_action_schema() -> dict:
    return {
        "name": "ai-tool-actions",
        "version": "1",
        "root": "tool",
        "nodes": {
            "tool": {
                "type": "choice", "field": "tool",
                "branches": [
                    {"value": "search", "target": "search_scope"},
                    {"value": "calendar", "target": "calendar_action"},
                    {"value": "email", "target": "email_action"},
                    {"value": "database", "target": "database_table"},
                ],
            },
            "search_scope": {
                "type": "choice", "field": "scope",
                "branches": [
                    {"value": "web", "target": "search_depth"},
                    {"value": "files", "target": "search_depth"},
                    {"value": "repository", "target": "search_depth"},
                ],
            },
            "search_depth": {"type": "range", "field": "depth", "start": 1, "stop": 5, "target": "end"},
            "calendar_action": {
                "type": "choice", "field": "action",
                "branches": [
                    {"value": "read", "target": "calendar_window"},
                    {"value": "create", "target": "calendar_duration"},
                    {"value": "update", "target": "calendar_duration"},
                ],
            },
            "calendar_window": {"type": "range", "field": "days", "start": 1, "stop": 7, "target": "end"},
            "calendar_duration": {"type": "range", "field": "duration_bucket", "start": 0, "stop": 5, "target": "end"},
            "email_action": {
                "type": "choice", "field": "action",
                "branches": [
                    {"value": "search", "target": "email_limit"},
                    {"value": "draft", "target": "email_tone"},
                    {"value": "send", "target": "email_recipient_count"},
                ],
            },
            "email_limit": {"type": "range", "field": "limit", "start": 1, "stop": 10, "target": "end"},
            "email_tone": {"type": "range", "field": "tone", "start": 0, "stop": 3, "target": "end"},
            "email_recipient_count": {"type": "range", "field": "recipients", "start": 1, "stop": 5, "target": "end"},
            "database_table": {"type": "range", "field": "table", "start": 0, "stop": 7, "target": "database_operation"},
            "database_operation": {
                "type": "choice", "field": "operation",
                "branches": [
                    {"value": "read", "target": "end"},
                    {"value": "insert", "target": "end"},
                    {"value": "update", "target": "end"},
                ],
            },
            "end": {"type": "terminal"},
        },
    }


def telecom_schema() -> dict:
    return {
        "name": "telecom-control-message",
        "version": "1",
        "root": "message_type",
        "nodes": {
            "message_type": {
                "type": "choice", "field": "message_type",
                "branches": [
                    {"value": "attach", "target": "attach_version"},
                    {"value": "data", "target": "data_bearer"},
                    {"value": "handover", "target": "handover_source"},
                    {"value": "emergency", "target": "emergency_service"},
                ],
            },
            "attach_version": {"type": "range", "field": "version", "start": 0, "stop": 3, "target": "attach_device"},
            "attach_device": {"type": "range", "field": "device_class", "start": 0, "stop": 15, "target": "attach_security"},
            "attach_security": {"type": "range", "field": "security", "start": 0, "stop": 7, "target": "end"},
            "data_bearer": {"type": "range", "field": "bearer", "start": 0, "stop": 7, "target": "data_qos"},
            "data_qos": {"type": "range", "field": "qos", "start": 0, "stop": 8, "target": "data_payload"},
            "data_payload": {"type": "range", "field": "payload_bucket", "start": 0, "stop": 63, "target": "end"},
            "handover_source": {"type": "range", "field": "source_region", "start": 0, "stop": 5, "target": "handover_target"},
            "handover_target": {"type": "range", "field": "target_region", "start": 0, "stop": 5, "target": "handover_cause"},
            "handover_cause": {"type": "range", "field": "cause", "start": 0, "stop": 11, "target": "end"},
            "emergency_service": {"type": "range", "field": "service", "start": 0, "stop": 3, "target": "emergency_priority"},
            "emergency_priority": {"type": "range", "field": "priority", "start": 0, "stop": 2, "target": "end"},
            "end": {"type": "terminal"},
        },
    }


def compiler_ast_schema() -> dict:
    return {
        "name": "bounded-expression-ast",
        "version": "1",
        "root": "expression_type",
        "nodes": {
            "expression_type": {
                "type": "choice", "field": "expression_type",
                "branches": [
                    {"value": "literal", "target": "literal_kind"},
                    {"value": "variable", "target": "variable_id"},
                    {"value": "unary", "target": "unary_op"},
                    {"value": "binary", "target": "binary_op"},
                    {"value": "call", "target": "call_function"},
                ],
            },
            "literal_kind": {
                "type": "choice", "field": "literal_kind",
                "branches": [
                    {"value": "int", "target": "literal_int"},
                    {"value": "bool", "target": "literal_bool"},
                    {"value": "string", "target": "literal_string"},
                ],
            },
            "literal_int": {"type": "range", "field": "value", "start": 0, "stop": 255, "target": "end"},
            "literal_bool": {"type": "range", "field": "value", "start": 0, "stop": 1, "target": "end"},
            "literal_string": {"type": "range", "field": "atom", "start": 0, "stop": 31, "target": "end"},
            "variable_id": {"type": "range", "field": "identifier", "start": 0, "stop": 127, "target": "end"},
            "unary_op": {"type": "range", "field": "operator", "start": 0, "stop": 3, "target": "unary_operand"},
            "unary_operand": {"type": "range", "field": "operand_class", "start": 0, "stop": 5, "target": "end"},
            "binary_op": {"type": "range", "field": "operator", "start": 0, "stop": 11, "target": "binary_left"},
            "binary_left": {"type": "range", "field": "left_class", "start": 0, "stop": 5, "target": "binary_right"},
            "binary_right": {"type": "range", "field": "right_class", "start": 0, "stop": 5, "target": "end"},
            "call_function": {"type": "range", "field": "function", "start": 0, "stop": 31, "target": "call_arity"},
            "call_arity": {
                "type": "choice", "field": "arity",
                "branches": [
                    {"value": "zero", "target": "end"},
                    {"value": "one", "target": "call_arg0_one"},
                    {"value": "two", "target": "call_arg0_two"},
                ],
            },
            "call_arg0_one": {"type": "range", "field": "arg0", "start": 0, "stop": 63, "target": "end"},
            "call_arg0_two": {"type": "range", "field": "arg0", "start": 0, "stop": 63, "target": "call_arg1_two"},
            "call_arg1_two": {"type": "range", "field": "arg1", "start": 0, "stop": 63, "target": "end"},
            "end": {"type": "terminal"},
        },
    }


def administrative_schema() -> dict:
    return {
        "name": "administrative-service-code",
        "version": "1",
        "root": "country",
        "nodes": {
            "country": {
                "type": "choice", "field": "country",
                "branches": [
                    {"value": "india", "target": "india_state"},
                    {"value": "belgium", "target": "belgium_region"},
                    {"value": "uae", "target": "uae_emirate"},
                    {"value": "singapore", "target": "singapore_district"},
                    {"value": "brazil", "target": "brazil_state"},
                ],
            },
            "india_state": {"type": "range", "field": "state", "start": 0, "stop": 35, "target": "india_district"},
            "india_district": {"type": "range", "field": "district", "start": 0, "stop": 49, "target": "india_office"},
            "india_office": {"type": "range", "field": "office", "start": 0, "stop": 7, "target": "end"},
            "belgium_region": {"type": "range", "field": "region", "start": 0, "stop": 2, "target": "belgium_province"},
            "belgium_province": {"type": "range", "field": "province", "start": 0, "stop": 9, "target": "belgium_commune"},
            "belgium_commune": {"type": "range", "field": "commune", "start": 0, "stop": 19, "target": "end"},
            "uae_emirate": {"type": "range", "field": "emirate", "start": 0, "stop": 6, "target": "uae_authority"},
            "uae_authority": {"type": "range", "field": "authority", "start": 0, "stop": 11, "target": "uae_service"},
            "uae_service": {"type": "range", "field": "service", "start": 0, "stop": 31, "target": "end"},
            "singapore_district": {"type": "range", "field": "district", "start": 0, "stop": 4, "target": "singapore_agency"},
            "singapore_agency": {"type": "range", "field": "agency", "start": 0, "stop": 15, "target": "singapore_service"},
            "singapore_service": {"type": "range", "field": "service", "start": 0, "stop": 15, "target": "end"},
            "brazil_state": {"type": "range", "field": "state", "start": 0, "stop": 26, "target": "brazil_municipality"},
            "brazil_municipality": {"type": "range", "field": "municipality_bucket", "start": 0, "stop": 99, "target": "brazil_service"},
            "brazil_service": {"type": "range", "field": "service", "start": 0, "stop": 7, "target": "end"},
            "end": {"type": "terminal"},
        },
    }


def fuzz_target_schema() -> dict:
    return {
        "name": "fuzz-target-domain",
        "version": "1",
        "root": "family",
        "nodes": {
            "family": {
                "type": "choice", "field": "family",
                "branches": [
                    {"value": "common", "target": "common_category"},
                    {"value": "medium", "target": "medium_category"},
                    {"value": "rare", "target": "rare_subtype"},
                    {"value": "singleton", "target": "end"},
                ],
            },
            "common_category": {"type": "range", "field": "category", "start": 0, "stop": 7, "target": "common_id"},
            "common_id": {"type": "range", "field": "id", "start": 0, "stop": 999, "target": "end"},
            "medium_category": {"type": "range", "field": "category", "start": 0, "stop": 3, "target": "medium_id"},
            "medium_id": {"type": "range", "field": "id", "start": 0, "stop": 199, "target": "end"},
            "rare_subtype": {
                "type": "choice", "field": "subtype",
                "branches": [
                    {"value": "tiny", "target": "rare_tiny"},
                    {"value": "small", "target": "rare_small"},
                    {"value": "large", "target": "rare_large"},
                ],
            },
            "rare_tiny": {"type": "range", "field": "id", "start": 0, "stop": 9, "target": "end"},
            "rare_small": {"type": "range", "field": "id", "start": 0, "stop": 99, "target": "end"},
            "rare_large": {"type": "range", "field": "id", "start": 0, "stop": 999, "target": "end"},
            "end": {"type": "terminal"},
        },
    }


def main() -> None:
    SCHEMAS.mkdir(parents=True, exist_ok=True)
    write("permit.json", permit_schema())
    write("calendar.json", calendar_schema(2024, 2025))
    write("ai_actions.json", ai_action_schema())
    write("telecom.json", telecom_schema())
    write("compiler_ast.json", compiler_ast_schema())
    write("administrative.json", administrative_schema())
    write("fuzz_target.json", fuzz_target_schema())


if __name__ == "__main__":
    main()
