# Path-Dependent Radix Spaces

PDRS compiles a finite dependent schema into an exact integer domain. Every valid structured object has one canonical rank in `0..N-1`, and every rank decodes to exactly one valid object.

Version 0.3 adds independent C11 and Rust 2021 implementations and cross-language evidence. The paper itself remains outside this release scope.

## Verified core

- exact subtree cardinality
- canonical rank and unrank
- finite acyclic DAG support
- deterministic schema hashes
- uniform sampling by rank
- exact disjoint worker partitions
- iterative validation for deep schemas
- explicit node, depth, range, and domain-bit limits
- research structured-domain permutation adapter with authentication
- independent Python, C, and Rust implementations of rank and unrank

## Evidence bundle

The committed evidence covers:

- 7 realistic schema families
- 1,000 generated schemas
- 254,609 Python-reference checks with zero rank/unrank failures
- 389,754 exhaustive C and Rust round trips with zero failures
- 22,096 deterministic cross-language vectors with zero mismatches
- C compilation with strict warnings, AddressSanitizer, and UndefinedBehaviorSanitizer
- Rust formatting, Clippy with warnings denied, and optimized release compilation
- encoding density against local UPER-style packing, protobuf wire format, JSON, and naive fixed fields
- controlled Python, C, and Rust runtime measurements
- median native rank speedups of 49.4x for C and 62.7x for Rust relative to Python in the committed GitHub-runner dataset
- median native unrank speedups of 136.5x for C and 38.8x for Rust relative to Python in the committed GitHub-runner dataset
- 750,000 uniformity samples
- 560 comparative fuzzing runs
- 6 schema evolution mutations
- single-bit fault injection
- resource exhaustion and timing tests
- 4 structured-domain permutation evaluations
- 14 committed SVG graphs and 14 PNG copies
- raw data, processed tables, environment metadata, and SHA-256 checksums

Read [`docs/EVIDENCE_REPORT.md`](docs/EVIDENCE_REPORT.md), [`native/README.md`](native/README.md), and [`results/processed/SUMMARY.md`](results/processed/SUMMARY.md).

## Reproduction

```bash
python -m pip install -r requirements-experiments.txt
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python scripts/verify_theorems.py --schemas 1000

for stage in correctness density runtime uniformity fuzzing schema_evolution fault_propagation scalability_and_timing crypto_adapter; do
  PYTHONPATH=src python scripts/run_full_experiments.py --stage "$stage"
done

PYTHONPATH=src python scripts/native_evidence.py prepare
make -C native/c
make -C native/c sanitize
cargo fmt --manifest-path native/rust/Cargo.toml -- --check
cargo clippy --manifest-path native/rust/Cargo.toml --all-targets -- -D warnings
cargo build --release --manifest-path native/rust/Cargo.toml
PYTHONPATH=src python scripts/native_evidence.py run \
  --c native/c/pdrs-c \
  --rust native/rust/target/release/pdrs-native \
  --iterations 200000

python scripts/assemble_evidence.py
PYTHONPATH=src python scripts/derive_tables.py
python scripts/assemble_evidence.py
python scripts/verify_evidence.py
```

Use `--quick` on every Python experiment stage for the CI-sized run, or run `make evidence-quick`.

## Important boundaries

- The proofs apply to the declared finite acyclic choice/range/terminal schema class.
- Runtime and timing results are hardware, compiler, interpreter, and runner dependent.
- The C and Rust engines consume a canonical IR emitted from validated JSON schemas rather than independently parsing the full JSON schema language.
- Native cardinalities are currently limited to unsigned 64-bit domains; the Python reference supports arbitrary-precision cardinalities.
- The protobuf comparison is a valid generic protobuf wire-format encoding, not a hand-optimized `.proto` for every schema.
- The UPER comparison implements the relevant CHOICE and fully constrained whole-number subset, not the entire ASN.1 specification.
- Dense ranks have weak intrinsic error detection and require checksums, authentication, or an outer integrity layer.
- Rank stability under schema evolution is conditional. Early insertions can move every rank.
- The included Feistel adapter is a research construction. It is not a standardized or deployment-ready encryption product.
