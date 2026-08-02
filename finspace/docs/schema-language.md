# Schema language

FinSpace deliberately supports finite declarative domains. Every active field must have a finite list of JSON-compatible values.

## Unconditional fields

```yaml
- name: currency
  values: [USD, EUR, INR]
```

## Dependent values

```yaml
- name: rate
  depends_on: currency
  cases:
    - equals: USD
      values: [0.00, 0.01, 0.03, 0.05]
    - equals: EUR
      values: [-0.01, 0.00, 0.02]
    - equals: INR
      values: [0.04, 0.06, 0.08]
```

A `default` list may be supplied for dependency values without an explicit case.

## Conditional fields

```yaml
- name: price
  values: [90.0, 100.0, 110.0]
  when:
    order_type: [limit, stop_limit]
```

Multiple conditions are conjunctive.

```yaml
when:
  instrument: [option]
  currency: [USD, EUR]
```

## Programmatic constructors

```python
Field.enum("currency", ["USD", "EUR"])
Field.integer("maturity_days", 1, 365, step=7)
Field.dependent("rate", "currency", {"USD": [0.01], "EUR": [0.0]})
```

## Ordering rule

A field may reference only earlier fields. This keeps the schema acyclic and its domain exactly countable.

## Values

Values must be finite JSON values:

- strings
- integers
- finite floats
- booleans
- null

Dates, decimals, enums, and custom classes should be represented by stable strings or integers and converted by an application adapter.

## Schema identity

`Schema.hash` is computed from canonical high-level schema JSON. Store it with results and checkpoints. Editing field order, values, conditions, or metadata changes the hash.

Ranks are stable only inside one exact schema version.
