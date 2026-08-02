"""QuantLib adapters for FinSpace records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Mapping

from ..errors import MissingOptionalDependency


@dataclass
class QuantLibEuropeanOptionPricer:
    """Callable QuantLib pricer for records from ``european_option_space``."""

    evaluation_date: date = date(2026, 8, 2)
    binomial_steps: int = 801
    fd_time_steps: int = 200
    fd_grid_points: int = 200

    def _ql(self) -> Any:
        try:
            import QuantLib as ql
        except ImportError as error:
            raise MissingOptionalDependency("install finspace[quantlib]") from error
        return ql

    def __call__(self, record: Mapping[str, Any]) -> dict[str, Any]:
        ql = self._ql()
        today = ql.Date(self.evaluation_date.day, self.evaluation_date.month, self.evaluation_date.year)
        ql.Settings.instance().evaluationDate = today
        maturity = today + int(record["maturity_days"])
        day_count = ql.Actual365Fixed()
        calendar = ql.NullCalendar()
        spot = ql.QuoteHandle(ql.SimpleQuote(float(record["spot"])))
        rate = ql.YieldTermStructureHandle(ql.FlatForward(today, float(record["rate"]), day_count))
        dividend = ql.YieldTermStructureHandle(
            ql.FlatForward(today, float(record.get("dividend", 0.0)), day_count)
        )
        volatility = ql.BlackVolTermStructureHandle(
            ql.BlackConstantVol(today, calendar, float(record["volatility"]), day_count)
        )
        process = ql.BlackScholesMertonProcess(spot, dividend, rate, volatility)
        option_type = ql.Option.Call if record["option_type"] == "call" else ql.Option.Put
        payoff = ql.PlainVanillaPayoff(option_type, float(record["strike"]))
        option = ql.VanillaOption(payoff, ql.EuropeanExercise(maturity))
        engine = str(record.get("engine", "analytic"))
        if engine == "analytic":
            option.setPricingEngine(ql.AnalyticEuropeanEngine(process))
        elif engine == "binomial":
            option.setPricingEngine(ql.BinomialVanillaEngine(process, "crr", self.binomial_steps))
        elif engine == "finite_difference":
            option.setPricingEngine(
                ql.FdBlackScholesVanillaEngine(process, self.fd_time_steps, self.fd_grid_points)
            )
        else:
            raise ValueError(f"unsupported QuantLib engine {engine!r}")
        return {
            "npv": float(option.NPV()),
            "delta": float(option.delta()),
            "gamma": float(option.gamma()),
            "vega": float(option.vega()) if engine == "analytic" else None,
            "engine": engine,
            "currency": record.get("currency"),
        }
