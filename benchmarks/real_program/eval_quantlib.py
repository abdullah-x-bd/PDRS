from __future__ import annotations

import math
import random
import time
from typing import Any, Sequence

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
    summarize_numbers,
    timed_generate,
    worker_overlap,
    write_csv,
    write_json,
)
from .schemas import quantlib_schema

RATES = [-0.01, 0.00, 0.01, 0.03, 0.05, 0.08]
MATURITIES = [7, 30, 90, 180, 365, 730]
VOLS = [0.05, 0.10, 0.15, 0.25, 0.40, 0.80]
DIVIDENDS = [0.00, 0.01, 0.03, 0.07]


def _decode(value: Sequence[str | int], rank: int) -> dict[str, Any]:
    tokens = list(value)
    if len(tokens) != 10:
        raise AssertionError(f"unexpected QuantLib token count {len(tokens)}: {tokens}")
    option_type, currency, rate_index, spot_index, strike_index, maturity_class, maturity_index, vol_index, dividend_index, engine_profile = tokens
    return {
        "rank": rank,
        "option_type": str(option_type),
        "currency": str(currency),
        "rate": RATES[int(rate_index)],
        "spot": 50.0 + 5.0 * int(spot_index),
        "strike": 50.0 + 5.0 * int(strike_index),
        "maturity_class": str(maturity_class),
        "maturity_days": MATURITIES[int(maturity_index)],
        "volatility": VOLS[int(vol_index)],
        "dividend": DIVIDENDS[int(dividend_index)],
        "engine_profile": str(engine_profile),
    }


def _normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def _black_scholes(case: dict[str, Any], option_type: str | None = None) -> float:
    kind = option_type or str(case["option_type"])
    spot = float(case["spot"])
    strike = float(case["strike"])
    maturity = float(case["maturity_days"]) / 365.0
    rate = float(case["rate"])
    dividend = float(case["dividend"])
    volatility = float(case["volatility"])
    root_t = math.sqrt(maturity)
    d1 = (math.log(spot / strike) + (rate - dividend + 0.5 * volatility * volatility) * maturity) / (volatility * root_t)
    d2 = d1 - volatility * root_t
    discounted_spot = spot * math.exp(-dividend * maturity)
    discounted_strike = strike * math.exp(-rate * maturity)
    if kind == "call":
        return discounted_spot * _normal_cdf(d1) - discounted_strike * _normal_cdf(d2)
    return discounted_strike * _normal_cdf(-d2) - discounted_spot * _normal_cdf(-d1)


def _quantlib_price(ql: Any, case: dict[str, Any], engine: str, option_type: str | None = None) -> float:
    today = ql.Date(2, ql.August, 2026)
    ql.Settings.instance().evaluationDate = today
    maturity = today + int(case["maturity_days"])
    day_count = ql.Actual365Fixed()
    calendar = ql.NullCalendar()
    spot = ql.QuoteHandle(ql.SimpleQuote(float(case["spot"])))
    risk_free = ql.YieldTermStructureHandle(ql.FlatForward(today, float(case["rate"]), day_count))
    dividend = ql.YieldTermStructureHandle(ql.FlatForward(today, float(case["dividend"]), day_count))
    volatility = ql.BlackVolTermStructureHandle(ql.BlackConstantVol(today, calendar, float(case["volatility"]), day_count))
    process = ql.BlackScholesMertonProcess(spot, dividend, risk_free, volatility)
    kind = option_type or str(case["option_type"])
    payoff = ql.PlainVanillaPayoff(ql.Option.Call if kind == "call" else ql.Option.Put, float(case["strike"]))
    option = ql.VanillaOption(payoff, ql.EuropeanExercise(maturity))
    if engine == "analytic":
        option.setPricingEngine(ql.AnalyticEuropeanEngine(process))
    elif engine == "binomial":
        option.setPricingEngine(ql.BinomialVanillaEngine(process, "crr", 801))
    elif engine == "finite_difference":
        option.setPricingEngine(ql.FdBlackScholesVanillaEngine(process, 200, 200))
    else:
        raise ValueError(engine)
    return float(option.NPV())


def _oracle_case(ql: Any, case: dict[str, Any], value: Sequence[str | int]) -> tuple[dict[str, Any], list[Failure]]:
    rank = int(case["rank"])
    failures: list[Failure] = []
    started = time.perf_counter()
    try:
        analytic = _quantlib_price(ql, case, "analytic")
        formula = _black_scholes(case)
        analytic_error = abs(analytic - formula)
        if not math.isfinite(analytic):
            failures.append(Failure("quantlib", rank, "finite", f"non-finite analytic price {analytic}", value))
        if analytic_error > 2e-10:
            failures.append(Failure("quantlib", rank, "black_scholes_formula", f"absolute error {analytic_error:.12g}", value))
        maturity = float(case["maturity_days"]) / 365.0
        discounted_spot = float(case["spot"]) * math.exp(-float(case["dividend"]) * maturity)
        discounted_strike = float(case["strike"]) * math.exp(-float(case["rate"]) * maturity)
        if case["option_type"] == "call":
            lower, upper = max(0.0, discounted_spot - discounted_strike), discounted_spot
        else:
            lower, upper = max(0.0, discounted_strike - discounted_spot), discounted_strike
        if analytic < lower - 1e-10 or analytic > upper + 1e-10:
            failures.append(Failure("quantlib", rank, "no_arbitrage_bounds", f"price {analytic}, bounds [{lower}, {upper}]", value))
        other_type = "put" if case["option_type"] == "call" else "call"
        other = _quantlib_price(ql, case, "analytic", other_type)
        call = analytic if case["option_type"] == "call" else other
        put = other if case["option_type"] == "call" else analytic
        parity_error = abs((call - put) - (discounted_spot - discounted_strike))
        if parity_error > 2e-10:
            failures.append(Failure("quantlib", rank, "put_call_parity", f"absolute error {parity_error:.12g}", value))
        binomial_error = math.nan
        fd_error = math.nan
        if case["engine_profile"] == "cross_engine":
            binomial = _quantlib_price(ql, case, "binomial")
            finite_difference = _quantlib_price(ql, case, "finite_difference")
            binomial_error = abs(binomial - analytic)
            fd_error = abs(finite_difference - analytic)
            if binomial_error > max(0.03, abs(analytic) * 0.004):
                failures.append(Failure("quantlib", rank, "binomial_agreement", f"absolute error {binomial_error:.12g}", value))
            if fd_error > max(0.03, abs(analytic) * 0.004):
                failures.append(Failure("quantlib", rank, "finite_difference_agreement", f"absolute error {fd_error:.12g}", value))
        return {
            "rank": rank,
            "option_type": case["option_type"],
            "currency": case["currency"],
            "analytic": analytic,
            "formula": formula,
            "analytic_error": analytic_error,
            "parity_error": parity_error,
            "binomial_error": binomial_error,
            "finite_difference_error": fd_error,
            "engine_profile": case["engine_profile"],
            "elapsed_ms": (time.perf_counter() - started) * 1000.0,
            "failures": len(failures),
        }, failures
    except Exception as error:
        failures.append(Failure("quantlib", rank, "exception", f"{type(error).__name__}: {error}", value))
        return {
            "rank": rank,
            "option_type": case["option_type"],
            "currency": case["currency"],
            "analytic": math.nan,
            "formula": math.nan,
            "analytic_error": math.nan,
            "parity_error": math.nan,
            "binomial_error": math.nan,
            "finite_difference_error": math.nan,
            "engine_profile": case["engine_profile"],
            "elapsed_ms": (time.perf_counter() - started) * 1000.0,
            "failures": 1,
        }, failures


def _metamorphic(ql: Any, cases: Sequence[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[Failure]]:
    rows: list[dict[str, Any]] = []
    failures: list[Failure] = []
    for case in cases:
        rank = int(case["rank"])
        try:
            base = _quantlib_price(ql, case, "analytic")
            bumped_spot = dict(case, spot=float(case["spot"]) + 1.0)
            bumped_strike = dict(case, strike=float(case["strike"]) + 1.0)
            doubled = dict(case, spot=float(case["spot"]) * 2.0, strike=float(case["strike"]) * 2.0)
            spot_price = _quantlib_price(ql, bumped_spot, "analytic")
            strike_price = _quantlib_price(ql, bumped_strike, "analytic")
            doubled_price = _quantlib_price(ql, doubled, "analytic")
            spot_ok = spot_price >= base - 1e-10 if case["option_type"] == "call" else spot_price <= base + 1e-10
            strike_ok = strike_price <= base + 1e-10 if case["option_type"] == "call" else strike_price >= base - 1e-10
            homogeneity_error = abs(doubled_price - 2.0 * base)
            if not spot_ok:
                failures.append(Failure("quantlib", rank, "spot_monotonicity", f"base={base}, bumped={spot_price}", None))
            if not strike_ok:
                failures.append(Failure("quantlib", rank, "strike_monotonicity", f"base={base}, bumped={strike_price}", None))
            if homogeneity_error > 2e-8:
                failures.append(Failure("quantlib", rank, "homogeneity", f"absolute error {homogeneity_error:.12g}", None))
            rows.append({"rank": rank, "spot_ok": spot_ok, "strike_ok": strike_ok, "homogeneity_error": homogeneity_error})
        except Exception as error:
            failures.append(Failure("quantlib", rank, "metamorphic_exception", f"{type(error).__name__}: {error}", None))
    return rows, failures


def run(budget: int = 2400, seed: int = 20260802) -> dict[str, Any]:
    import QuantLib as ql

    schema = CompiledSchema(quantlib_schema())
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
        generation_rows.append({"evaluation": "quantlib", "method": method, **generation_metrics(values, elapsed)})
    values = generated["pdrs_without_replacement"]
    cases = [_decode(value, schema.rank(value)) for value in values]
    result_rows: list[dict[str, Any]] = []
    failures: list[Failure] = []
    for value, case in zip(values, cases):
        row, local_failures = _oracle_case(ql, case, value)
        result_rows.append(row)
        failures.extend(local_failures)
    metamorphic_rows, metamorphic_failures = _metamorphic(ql, cases[:min(600, len(cases))])
    failures.extend(metamorphic_failures)
    write_csv(RAW / "quantlib_generation.csv", generation_rows)
    write_csv(RAW / "quantlib_oracles.csv", result_rows)
    write_csv(RAW / "quantlib_metamorphic.csv", metamorphic_rows)
    write_json(FAILURES / "quantlib_failures.json", [failure.as_dict() for failure in failures])
    cross = [row for row in result_rows if row["engine_profile"] == "cross_engine" and math.isfinite(float(row["analytic_error"]))]
    summary = {
        "package": "QuantLib",
        "package_version": getattr(ql, "__version__", "1.43"),
        "schema_count": schema.count,
        "schema_hash": schema.canonical_hash,
        "budget": budget,
        "generation": generation_rows,
        "priced": len(result_rows),
        "cross_engine_cases": len(cross),
        "oracle_failures": len(failures),
        "analytic_error": summarize_numbers([float(row["analytic_error"]) for row in result_rows if math.isfinite(float(row["analytic_error"]))]),
        "put_call_parity_error": summarize_numbers([float(row["parity_error"]) for row in result_rows if math.isfinite(float(row["parity_error"]))]),
        "binomial_error": summarize_numbers([float(row["binomial_error"]) for row in cross if math.isfinite(float(row["binomial_error"]))]),
        "finite_difference_error": summarize_numbers([float(row["finite_difference_error"]) for row in cross if math.isfinite(float(row["finite_difference_error"]))]),
        "pricing_latency_ms": summarize_numbers([float(row["elapsed_ms"]) for row in result_rows]),
        "metamorphic_cases": len(metamorphic_rows),
        **worker_overlap(schema, workers=8, per_worker=1000, seed=seed),
    }
    write_json(PROCESSED / "quantlib_summary.json", summary)
    return summary
