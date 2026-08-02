# Release and deployment

## Build

```bash
python -m build finspace
```

## Verify the wheel

```bash
python -m venv /tmp/finspace-wheel
/tmp/finspace-wheel/bin/pip install dist/finspace-*.whl
/tmp/finspace-wheel/bin/finspace --version
```

## Versioning

FinSpace follows semantic versioning. Alpha releases may adjust APIs, but schema hashes and rank behavior remain deterministic for the exact installed version and schema document.

## PyPI prerequisites

The `pdrs` distribution must be published before the public `finspace` wheel because it is a declared runtime dependency.

## Recommended production record

Store:

```json
{
  "finspace_version": "0.1.0",
  "pdrs_version": "0.2.0",
  "schema_hash": "...",
  "engine_hash": "...",
  "rank": 123456
}
```
