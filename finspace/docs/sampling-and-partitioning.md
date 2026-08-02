# Sampling and partitioning

## Object-uniform sampling

```python
space.sample(1000, replace=False, seed=42)
```

Every complete valid object has equal probability. Without replacement, every selected rank is distinct.

## Replacement sampling

```python
space.sample(1000, replace=True, seed=42)
```

This is useful for conventional Monte Carlo-style draws but can duplicate records.

## Stratified sampling

```python
space.sample_stratified("message_type", 1000, seed=42)
```

Stratification balances the campaign across an unconditional field. Within each stratum, objects are sampled uniformly without replacement.

Use it when branch or product-family coverage matters more than global object uniformity.

## Conditioning

```python
usd = space.condition(currency="USD")
```

The conditioned space has its own exact count and can still rank, unrank, sample, and partition records. Records remain rankable in the parent space.

## Exact partitions

For `w` workers, worker `i` receives:

```text
[floor(i*N/w), floor((i+1)*N/w))
```

The intervals are contiguous, disjoint, and cover `[0, N)`.

```python
for partition in space.partitions(32):
    submit(partition.start, partition.stop)
```

## Reproducibility

Persist:

- high-level schema hash
- engine hash
- rank or rank interval
- package version
- application version

That is sufficient to reconstruct the exact FinSpace record, subject to retaining the same schema and decoding adapters.
