# Limitations and safety

## Finite domains only

FinSpace requires finite explicit value sets. Unbounded strings, arbitrary real numbers, and unrestricted recursive objects must be converted into bounded profiles.

## Exact counting can still be large

The object count may be enormous even when the compiled graph is compact. Complete enumeration is not automatically practical.

## Schema evolution

Ranks are canonical only for one exact schema. Inserting or reordering values can move many ranks. Always store the schema hash with a rank.

## Distribution objective

Object-uniform sampling is not the same as branch coverage, market realism, historical probability, or risk importance. Use stratification, conditioning, or application-defined weighting when appropriate.

FinSpace 0.1 does not yet implement arbitrary weighted finite-domain sampling.

## Numerical acceleration

FinSpace does not accelerate QuantLib formulas, Monte Carlo path arithmetic, or linear algebra. It reduces scenario-construction, deduplication, partitioning, and replay overhead.

## Protocol compliance

The included FIX and ISO 20022 adapters are examples and testing tools. Production deployments must follow the relevant counterparty, exchange, bank, network, and regulatory profiles.

## Security

Ranks can reveal domain size and relative position. They are not encrypted identifiers. Do not place sensitive records in public schemas. Use established authenticated encryption where confidentiality is required.

## Checkpoints

SQLite checkpoint results contain application outputs and tracebacks. Protect the file as operational data.
