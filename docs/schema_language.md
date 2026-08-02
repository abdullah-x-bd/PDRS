# Schema language version 0.1

A schema is a JSON object with `name`, `version`, `root`, and `nodes`.

## Terminal

```json
{"type": "terminal"}
```

A terminal contributes exactly one completion and consumes no token.

## Choice

```json
{
  "type": "choice",
  "field": "permit_type",
  "branches": [
    {"value": "research", "target": "research_district"},
    {"value": "transit", "target": "transit_port"}
  ]
}
```

Branch order is part of the canonical schema and therefore part of the rank definition.

## Inclusive range

```json
{
  "type": "range",
  "field": "serial",
  "start": 0,
  "stop": 99,
  "target": "end"
}
```

This represents 100 ordered choices.

## Canonical versioning

A stored rank must be paired with a schema identity or canonical hash. Ranks from different schema versions are not assumed compatible.
