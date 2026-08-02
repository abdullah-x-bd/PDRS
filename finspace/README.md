# FinSpace

**Exact, rank-addressable financial scenario and protocol spaces.**

FinSpace compiles a finite financial schema into one exact integer domain. Every valid record receives one canonical rank, and every rank decodes to one valid record.

```text
financial record  <---- exact bijection ---->  integer in [0, N)
```

That one integer can be used as a:

- reproducible scenario identifier
- cache and database key
- deterministic worker assignment
- test-case reproducer
- checkpoint coordinate
- source of duplicate-free samples
- position in complete finite-domain enumeration

FinSpace is powered by [PDRS](https://github.com/abdullah-x-bd/PDRS), whose rank/unrank engine has Python, C, and Rust conformance evidence.

## Why it exists

Financial testing and risk workflows frequently construct a Cartesian product and filter it afterward:

```python
for product in products:
    for currency in currencies:
        for maturity in maturities:
            for shock in shocks:
                scenario = build(...)
                if valid(scenario):
                    calculate(scenario)
```

This becomes expensive and operationally awkward when:

- valid choices depend on earlier fields
- most combinations are invalid
- millions of scenarios are divided between workers
- random workers duplicate expensive calculations
- a failed case must be reproduced exactly
- campaigns must resume after interruption

FinSpace compiles only the valid domain and addresses it directly:

```python
from finspace.templates import european_option_space

space = european_option_space()
print(space.count)

worker = space.partition(worker_id=3, worker_count=32)
for rank in worker:
    scenario = space.unrank(rank)
    result = price(scenario)
    save(rank, result)
```

## Installation

Once published:

```bash
pip install finspace
```

Optional integrations:

```bash
pip install "finspace[tabular]"
pip install "finspace[quantlib]"
pip install "finspace[fix]"
pip install "finspace[iso20022]"
pip install "finspace[all]"
```

From the current monorepo:

```bash
pip install "pdrs @ git+https://github.com/abdullah-x-bd/PDRS.git"
pip install "finspace[all] @ git+https://github.com/abdullah-x-bd/PDRS.git#subdirectory=finspace"
```

For development:

```bash
git clone https://github.com/abdullah-x-bd/PDRS.git
cd PDRS
pip install -e .
pip install -e "./finspace[dev,all]"
```

## Thirty-second example

```python
from finspace import Field, Schema, Space

schema = Schema(
    name="option-grid",
    fields=(
        Field.enum("option_type", ["call", "put"]),
        Field.enum("currency", ["USD", "EUR"]),
        Field.dependent(
            "rate",
            "currency",
            {
                "USD": [0.01, 0.03, 0.05],
                "EUR": [-0.01, 0.00, 0.02],
            },
        ),
        Field.enum("spot", [90.0, 100.0, 110.0]),
        Field.enum("strike", [90.0, 100.0, 110.0]),
        Field.enum("maturity_days", [30, 90, 365]),
    ),
)

space = Space(schema)
print(space.count)            # 324
print(space.schema_hash)      # stable high-level schema identity

record = {
    "option_type": "call",
    "currency": "USD",
    "rate": 0.03,
    "spot": 100.0,
    "strike": 110.0,
    "maturity_days": 90,
}

rank = space.rank(record)
assert space.unrank(rank) == record

samples = space.sample(100, replace=False, seed=42)
assert len({space.rank(item) for item in samples}) == 100
```

## Conditional fields

A FIX limit order requires a price; a market order does not.

```python
from finspace import Condition, Field, Schema, Space

orders = Space(
    Schema(
        name="orders",
        fields=(
            Field.enum("order_type", ["market", "limit", "stop_limit"]),
            Field.enum("symbol", ["AAPL", "MSFT"]),
            Field.enum(
                "price",
                [90.0, 100.0, 110.0],
                when=(Condition("order_type", ("limit", "stop_limit")),),
            ),
            Field.enum(
                "stop_price",
                [85.0, 95.0, 105.0],
                when=(Condition("order_type", ("stop_limit",)),),
            ),
        ),
    )
)

market = orders.unrank(0)
assert "price" not in market
```

## Sampling modes

### Exact object-uniform samples without replacement

```python
records = space.sample(10_000, replace=False, seed=7)
```

### Replacement sampling

```python
records = space.sample(10_000, replace=True, seed=7)
```

### Branch-balanced sampling

Object-uniform sampling can underrepresent a small top-level branch. FinSpace therefore exposes explicit stratification when branch coverage is the objective:

```python
records = space.sample_stratified(
    "instrument_type",
    10_000,
    seed=7,
)
```

The objective is explicit rather than hidden:

- `sample()` targets complete-object uniformity
- `sample_stratified()` targets balance across a named field

## Distributed work

```python
partitions = space.partitions(worker_count=8)

for partition in partitions:
    print(partition.start, partition.stop, len(partition))
```

The intervals are disjoint and cover the domain exactly.

```python
worker = space.partition(worker_id=2, worker_count=8)
for batch in worker.batches(10_000):
    records = space.unrank_many(batch)
    calculate_batch(records)
```

## Checkpointed execution

```python
from finspace.runner import Runner
from finspace.templates import european_option_space
from finspace.adapters.quantlib import QuantLibEuropeanOptionPricer

space = european_option_space()
runner = Runner(
    space,
    QuantLibEuropeanOptionPricer(),
    backend="thread",
    max_workers=8,
    checkpoint="option-results.sqlite",
    run_id="daily-risk-2026-08-02",
)

summary = runner.run(
    partition=space.partition(worker_id=0, worker_count=4),
    limit=50_000,
)
print(summary.to_dict())
```

Re-running the same command skips completed ranks. A checkpoint refuses to resume against a different schema hash.

## Tabular output

```python
from finspace import to_numpy, to_pandas, to_arrow

records = space.sample(1000, replace=False, seed=42)
arrays = to_numpy(records)
frame = to_pandas(records)
table = to_arrow(records)
```

## Finance integrations

### QuantLib

```python
from finspace.templates import european_option_space
from finspace.adapters import QuantLibEuropeanOptionPricer

space = european_option_space()
pricer = QuantLibEuropeanOptionPricer()

rank, scenario = space.sample(1, seed=10, with_ranks=True)[0]
result = pricer(scenario)
print(rank, result["npv"])
```

### SimpleFIX

```python
from finspace.templates import fix_order_space
from finspace.adapters import SimpleFixNewOrderSingleEncoder

space = fix_order_space()
record = space.sample(1, seed=10)[0]
record["client_order_id"] = "ORDER-0001"
encoded = SimpleFixNewOrderSingleEncoder()(record)
```

### ISO 20022

```python
from finspace.templates import iso20022_payment_space
from finspace.adapters import ISO20022PaymentBuilder

space = iso20022_payment_space()
record = space.sample(1, seed=10)[0]
xml = ISO20022PaymentBuilder()(record)
```

## CLI

```bash
finspace inspect examples/european_options.yaml
finspace sample examples/european_options.yaml -n 5 --seed 42
finspace sample examples/fix_orders.yaml -n 20 --stratify order_type
finspace rank examples/european_options.yaml scenario.json
finspace unrank examples/european_options.yaml 1234
finspace partition examples/european_options.yaml --workers 16 --worker 3
finspace export examples/european_options.yaml scenarios.jsonl --limit 1000
```

## What FinSpace accelerates

FinSpace can reduce work spent on:

- invalid Cartesian combinations
- rejection sampling
- duplicate scenario generation
- duplicate cross-worker calculations
- full-list materialization
- task coordination databases
- serialization-heavy cache keys
- manual replay bookkeeping

It does **not** make a pricing formula, matrix multiplication, or Monte Carlo path intrinsically faster. It orchestrates the finite scenario domain around those calculations.

## Evidence behind the package

The PDRS repository includes real-program evaluations against:

- SimpleFIX
- QuantLib
- ISO 20022 XSD validation

At 500,000 generated cases, exact no-replacement ranks avoided 35,604 repeated QuantLib scenarios and 28,031 repeated ISO 20022 scenarios. Eight deterministic partitions had zero overlap, while independent random workers overlapped by 20,078 QuantLib scenarios and 15,828 ISO scenarios in the tested configuration.

The same evaluation found that PDRS did not improve SimpleFIX code coverage at the matched budget. FinSpace therefore exposes both object-uniform and branch-stratified sampling rather than pretending one distribution solves every testing objective.

## Documentation

- [Quick start](docs/quickstart.md)
- [Schema language](docs/schema-language.md)
- [Sampling and partitioning](docs/sampling-and-partitioning.md)
- [Checkpointed runner](docs/runner.md)
- [Finance adapters](docs/adapters.md)
- [Architecture](docs/architecture.md)
- [Limitations and safety](docs/limitations.md)
- [Release and deployment](docs/releasing.md)

## Status

FinSpace 0.1 is an alpha release. Its public API is documented and tested, but users should pin the version and schema hash for production evaluation campaigns.
