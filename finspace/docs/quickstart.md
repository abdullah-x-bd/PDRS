# Quick start

## 1. Define a schema

A schema is an ordered tuple of finite fields. Later fields may depend on earlier fields or be active only under stated conditions.

```python
from finspace import Condition, Field, Schema, Space

schema = Schema(
    name="trade-scenarios",
    version="2026.08",
    fields=(
        Field.enum("instrument", ["bond", "option"]),
        Field.enum("currency", ["USD", "EUR", "INR"]),
        Field.dependent(
            "rate_shock_bp",
            "currency",
            {
                "USD": [-100, -50, 0, 50, 100],
                "EUR": [-100, -50, 0, 50],
                "INR": [-50, 0, 50, 100, 200],
            },
        ),
        Field.enum(
            "volatility_shock_bp",
            [-1000, -500, 0, 500, 1000],
            when=(Condition("instrument", ("option",)),),
        ),
    ),
)
space = Space(schema)
```

## 2. Inspect the domain

```python
print(space.describe())
```

`count` is exact. FinSpace does not construct every record to obtain it.

## 3. Address records

```python
record = {
    "instrument": "option",
    "currency": "USD",
    "rate_shock_bp": 50,
    "volatility_shock_bp": 500,
}

rank = space.rank(record)
assert space.unrank(rank) == record
```

## 4. Generate distinct scenarios

```python
records = space.sample(1000, replace=False, seed=42)
```

## 5. Divide work

```python
partition = space.partition(worker_id=1, worker_count=8)
for rank in partition:
    calculate(space.unrank(rank))
```

## 6. Resume work

```python
from finspace.runner import Runner

runner = Runner(
    space,
    calculate,
    checkpoint="trade-results.sqlite",
    run_id="stress-2026-08",
)
runner.run(partition=partition)
```
