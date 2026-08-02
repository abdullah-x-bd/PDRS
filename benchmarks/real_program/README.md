# Real-program finance evaluation

This campaign evaluates PDRS against three real financial software targets rather than synthetic seeded objects.

## Evaluation 1: SimpleFIX 1.0.17

The PDRS schema generates valid bounded FIX 4.4 profiles for:

- New Order Single (`D`)
- Order Cancel Request (`F`)
- Order Cancel/Replace Request (`G`)
- Market Data Request (`V`)

Each generated case is encoded by SimpleFIX, manually checked for BodyLength and CheckSum correctness, streamed through `FixParser` under six fragmentation strategies, parsed, and compared with the original semantic fields. Equal-budget PDRS-without-replacement, PDRS-with-replacement, and locally uniform grammar generation are compared for uniqueness, throughput, package coverage, and worker overlap. Controlled malformed messages test parser behavior for checksum, body length, truncation, missing BeginString, and empty fields.

## Evaluation 2: QuantLib 1.43

The scenario schema covers calls and puts, three currencies with dependent rate sets, 21 spot buckets, 21 strike buckets, six maturities, six volatility buckets, four dividend yields, and analytic or cross-engine profiles.

Every selected scenario is priced with `AnalyticEuropeanEngine` and compared with an independent Black-Scholes-Merton implementation, put-call parity, no-arbitrage bounds, and metamorphic properties. Cross-engine profiles additionally compare the analytic result with CRR binomial and finite-difference engines. The experiment records exact failure ranks and measures duplicate-free generation and parallel partitioning.

## Evaluation 3: ISO 20022

The workflow downloads the current official schemas directly from ISO 20022:

- `pain.001.001.13`, Customer Credit Transfer Initiation V13
- `pacs.008.001.14`, FI-to-FI Customer Credit Transfer V14

PDRS generates bounded valid payment profiles. Each XML document is independently validated with both lxml/libxml2 and the Python `xmlschema` implementation, decoded, and semantically checked. Controlled mutations remove required elements, alter currency and amount constraints, duplicate elements, or replace the namespace. The official XSDs are not committed; their source URLs and SHA-256 hashes are preserved with the evidence.

## Evidence

The workflow produces:

- raw CSV results for every case and method
- exact rank-addressed failure records
- processed JSON summaries
- package coverage reports
- environment metadata
- SHA-256 evidence checksums
- SVG and PNG figures

Run locally with:

```bash
python -m pip install -e .
python -m pip install -r benchmarks/real_program/requirements.txt
PYTHONPATH=src python -m benchmarks.real_program.run_all \
  --xsd-dir benchmarks/real_program/vendor
```

The XSD directory must contain `pain.001.001.13.xsd` and `pacs.008.001.14.xsd` downloaded from the official ISO 20022 catalogue.
