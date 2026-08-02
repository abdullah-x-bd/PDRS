from __future__ import annotations

from typing import Any


def _choice(field: str, branches: list[tuple[str, str]]) -> dict[str, Any]:
    return {
        "type": "choice",
        "field": field,
        "branches": [{"value": value, "target": target} for value, target in branches],
    }


def _range(field: str, start: int, stop: int, target: str) -> dict[str, Any]:
    return {"type": "range", "field": field, "start": start, "stop": stop, "target": target}


def simplefix_schema() -> dict[str, Any]:
    nodes: dict[str, Any] = {
        "root": _choice("message_type", [("D", "new_side"), ("F", "cancel_symbol"), ("G", "replace_side"), ("V", "md_subscription")]),
        "end": {"type": "terminal"},
        "fragment": _range("fragmentation", 0, 5, "end"),
        "symbol": _range("symbol", 0, 11, "quantity"),
        "quantity": _range("quantity", 0, 15, "time_in_force"),
        "time_in_force": _range("time_in_force", 0, 4, "fragment"),
        "price": _range("price", 0, 20, "time_in_force"),
        "stop_price": _range("stop_price", 0, 20, "time_in_force"),
        "price_then_stop": _range("price", 0, 20, "stop_after_price"),
        "stop_after_price": _range("stop_price", 0, 20, "time_in_force"),
        "new_side": _choice("side", [("1", "new_order_type"), ("2", "new_order_type")]),
        "new_order_type": _choice("order_type", [("1", "symbol"), ("2", "new_limit_symbol"), ("3", "new_stop_symbol"), ("4", "new_stop_limit_symbol")]),
        "new_limit_symbol": _range("symbol", 0, 11, "new_limit_quantity"),
        "new_limit_quantity": _range("quantity", 0, 15, "price"),
        "new_stop_symbol": _range("symbol", 0, 11, "new_stop_quantity"),
        "new_stop_quantity": _range("quantity", 0, 15, "stop_price"),
        "new_stop_limit_symbol": _range("symbol", 0, 11, "new_stop_limit_quantity"),
        "new_stop_limit_quantity": _range("quantity", 0, 15, "price_then_stop"),
        "cancel_symbol": _range("symbol", 0, 11, "cancel_side"),
        "cancel_side": _choice("side", [("1", "cancel_orig_id"), ("2", "cancel_orig_id")]),
        "cancel_orig_id": _range("orig_order_id", 0, 127, "fragment"),
        "replace_side": _choice("side", [("1", "replace_order_type"), ("2", "replace_order_type")]),
        "replace_order_type": _choice("order_type", [("1", "replace_symbol"), ("2", "replace_limit_symbol"), ("3", "replace_stop_symbol"), ("4", "replace_stop_limit_symbol")]),
        "replace_symbol": _range("symbol", 0, 11, "replace_quantity"),
        "replace_quantity": _range("quantity", 0, 15, "replace_orig_id"),
        "replace_orig_id": _range("orig_order_id", 0, 127, "time_in_force"),
        "replace_limit_symbol": _range("symbol", 0, 11, "replace_limit_quantity"),
        "replace_limit_quantity": _range("quantity", 0, 15, "replace_limit_price"),
        "replace_limit_price": _range("price", 0, 20, "replace_limit_orig"),
        "replace_limit_orig": _range("orig_order_id", 0, 127, "time_in_force"),
        "replace_stop_symbol": _range("symbol", 0, 11, "replace_stop_quantity"),
        "replace_stop_quantity": _range("quantity", 0, 15, "replace_stop_value"),
        "replace_stop_value": _range("stop_price", 0, 20, "replace_stop_orig"),
        "replace_stop_orig": _range("orig_order_id", 0, 127, "time_in_force"),
        "replace_stop_limit_symbol": _range("symbol", 0, 11, "replace_stop_limit_quantity"),
        "replace_stop_limit_quantity": _range("quantity", 0, 15, "replace_stop_limit_price"),
        "replace_stop_limit_price": _range("price", 0, 20, "replace_stop_limit_stop"),
        "replace_stop_limit_stop": _range("stop_price", 0, 20, "replace_stop_limit_orig"),
        "replace_stop_limit_orig": _range("orig_order_id", 0, 127, "time_in_force"),
        "md_subscription": _choice("subscription", [("0", "md_depth"), ("1", "md_depth"), ("2", "md_depth")]),
        "md_depth": _range("market_depth", 0, 9, "md_entries"),
        "md_entries": _choice("entry_set", [("BID", "md_symbol"), ("OFFER", "md_symbol"), ("BOTH", "md_symbol")]),
        "md_symbol": _range("symbol", 0, 11, "fragment"),
    }
    return {"name": "simplefix-real-program", "version": "1", "root": "root", "nodes": nodes}


def quantlib_schema() -> dict[str, Any]:
    # The profile is finite but large enough to make duplicate-free, rank-addressable
    # scenario generation useful. Currency controls a valid dependent rate set.
    nodes: dict[str, Any] = {
        "root": _choice("option_type", [("call", "currency"), ("put", "currency")]),
        "currency": _choice("currency", [("USD", "usd_rate"), ("EUR", "eur_rate"), ("JPY", "jpy_rate")]),
        "usd_rate": _range("rate_index", 1, 5, "spot"),
        "eur_rate": _range("rate_index", 0, 4, "spot"),
        "jpy_rate": _range("rate_index", 0, 3, "spot"),
        "spot": _range("spot_index", 0, 20, "strike"),
        "strike": _range("strike_index", 0, 20, "maturity_class"),
        "maturity_class": _choice("maturity_class", [("short", "short_maturity"), ("medium", "medium_maturity"), ("long", "long_maturity")]),
        "short_maturity": _range("maturity_index", 0, 1, "short_vol"),
        "short_vol": _range("vol_index", 1, 5, "dividend"),
        "medium_maturity": _range("maturity_index", 2, 3, "all_vol"),
        "long_maturity": _range("maturity_index", 4, 5, "all_vol"),
        "all_vol": _range("vol_index", 0, 5, "dividend"),
        "dividend": _range("dividend_index", 0, 3, "engine_profile"),
        "engine_profile": _choice("engine_profile", [("analytic", "end"), ("cross_engine", "end")]),
        "end": {"type": "terminal"},
    }
    return {"name": "quantlib-real-program", "version": "1", "root": "root", "nodes": nodes}


def iso20022_schema() -> dict[str, Any]:
    nodes: dict[str, Any] = {
        "root": _choice("message", [("pain.001.001.13", "pain_currency"), ("pacs.008.001.14", "pacs_currency")]),
        "pain_currency": _choice("currency", [("EUR", "pain_amount"), ("GBP", "pain_amount"), ("USD", "pain_amount")]),
        "pain_amount": _range("amount_bucket", 0, 24, "pain_debtor"),
        "pain_debtor": _range("debtor_index", 0, 7, "pain_creditor"),
        "pain_creditor": _range("creditor_index", 0, 7, "pain_exec_day"),
        "pain_exec_day": _range("execution_day", 3, 27, "pain_batch"),
        "pain_batch": _choice("batch_booking", [("true", "pain_remittance"), ("false", "pain_remittance")]),
        "pain_remittance": _range("remittance_index", 0, 15, "end"),
        "pacs_currency": _choice("currency", [("EUR", "pacs_amount"), ("GBP", "pacs_amount"), ("USD", "pacs_amount")]),
        "pacs_amount": _range("amount_bucket", 0, 24, "pacs_debtor"),
        "pacs_debtor": _range("debtor_index", 0, 7, "pacs_creditor"),
        "pacs_creditor": _range("creditor_index", 0, 7, "pacs_settlement_day"),
        "pacs_settlement_day": _range("settlement_day", 3, 27, "pacs_charge"),
        "pacs_charge": _choice("charge_bearer", [("SLEV", "pacs_priority"), ("SHAR", "pacs_priority")]),
        "pacs_priority": _choice("priority", [("NORM", "end"), ("HIGH", "end")]),
        "end": {"type": "terminal"},
    }
    return {"name": "iso20022-real-program", "version": "1", "root": "root", "nodes": nodes}
