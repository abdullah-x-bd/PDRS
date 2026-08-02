from pathlib import Path

from finspace.adapters import QuantLibEuropeanOptionPricer
from finspace.runner import Runner
from finspace.templates import european_option_space

space = european_option_space()
runner = Runner(
    space,
    QuantLibEuropeanOptionPricer(),
    backend="thread",
    max_workers=4,
    checkpoint=Path("quantlib-results.sqlite"),
    run_id="example",
)

summary = runner.run(
    partition=space.partition(worker_id=0, worker_count=16),
    limit=100,
)
print(summary.to_dict())
