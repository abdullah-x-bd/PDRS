# Real-program finance evaluation results

This evidence evaluates PDRS against three real financial software targets. It is not a claim that PDRS found defects in all three packages or that object-uniform generation always maximizes code coverage.

## Environment

- Python 3.12.13
- SimpleFIX 1.0.17
- QuantLib 1.43
- xmlschema 4.3.2
- lxml 6.1.1
- GitHub-hosted Linux runner with 4 CPUs

The complete machine-readable summary is in `processed/real_program_summary.json`. Raw per-case data, failure ledgers, figures, XSD provenance, and SHA-256 checksums are committed beside this document.

## Evaluation 1: SimpleFIX

### Domain and workload

The compiled schema contains **719,287,632 valid bounded FIX configurations** spanning:

- New Order Single
- Order Cancel Request
- Order Cancel/Replace Request
- Market Data Request
- conditional price and stop-price fields
- order side, symbol, quantity, time-in-force, and six stream-fragmentation profiles

Three methods generated and executed 3,000 cases each.

| Method | Unique cases | Unique rate | Runtime package coverage | Valid-message oracle failures |
|---|---:|---:|---:|---:|
| PDRS without replacement | 3,000 | 100.00% | 11.62% | 0 |
| PDRS with replacement | 3,000 | 100.00% | 11.62% | 0 |
| Locally uniform grammar | 2,941 | 98.03% | 11.62% | 0 |

All 9,000 valid encoded messages passed manual BodyLength and CheckSum verification, fragmented stream parsing, and semantic field comparison.

### Important negative result

PDRS did **not** improve SimpleFIX package coverage at this budget. All methods reached the same measured runtime coverage. PDRS's object-uniform sampling was heavily concentrated in the much larger Cancel/Replace subdomain, while the locally uniform grammar balanced top-level message types. This confirms that object-uniformity and branch-coverage balance are different objectives.

PDRS did provide exact uniqueness for the no-replacement campaign and compact rank-addressed reproduction. At this small budget, replacement sampling happened not to collide because the domain is extremely large.

### Controlled malformed messages

Across 400 base messages per mutation:

- Missing BeginString and truncation produced no parsed message.
- Empty SenderCompID raised `EmptyValueError`.
- Bad CheckSum and bad BodyLength were still returned as parsed messages.

The last behavior is recorded as parser behavior, not automatically classified as a SimpleFIX bug. The library's parser is not assumed to be a full FIX session-level validator.

## Evaluation 2: QuantLib

### Domain and workload

The compiled financial scenario space contains **3,358,656 valid configurations** spanning:

- calls and puts
- USD, EUR, and JPY with currency-dependent rate sets
- 21 spot buckets
- 21 strike buckets
- six maturity buckets
- six volatility buckets
- four dividend yields
- analytic-only and cross-engine profiles

PDRS selected 1,200 unique scenarios without replacement. Every scenario was priced with QuantLib's analytic European engine and checked against an independent Black-Scholes-Merton implementation, put-call parity, and no-arbitrage bounds. Six hundred scenarios also received spot monotonicity, strike monotonicity, and homogeneity checks. A total of 606 scenarios were compared with CRR binomial and finite-difference engines.

### Results

- **1,200 priced scenarios**
- **606 cross-engine scenarios**
- **600 metamorphic scenarios**
- **0 oracle failures**

| Oracle | Median absolute error | 95th percentile | Maximum |
|---|---:|---:|---:|
| Analytic QuantLib vs independent formula | 4.88e-15 | 2.67e-14 | 1.21e-13 |
| Put-call parity | 7.11e-15 | 2.84e-14 | 6.75e-14 |
| CRR binomial vs analytic | 1.13e-4 | 4.58e-3 | 2.13e-2 |
| Finite difference vs analytic | 1.31e-4 | 8.30e-3 | 3.86e-2 |

The evaluation found no confirmed QuantLib defect. Its contribution is a reproducible, distributed, exact-domain differential-testing harness. Every evaluated scenario can be reconstructed from the schema hash and rank.

### Generation comparison

| Method | Unique cases from 1,200 | Generation rate |
|---|---:|---:|
| PDRS without replacement | 1,200 | about 363,000/s |
| PDRS with replacement | 1,200 | about 381,000/s |
| Locally uniform grammar | 1,199 | about 236,000/s |

These generation costs were tiny relative to QuantLib pricing latency. The practical advantage is campaign control, not a material acceleration of the pricing formula itself.

## Evaluation 3: ISO 20022

### Domain and workload

The bounded payment domain contains **4,320,000 valid configurations** for:

- `pain.001.001.13`
- `pacs.008.001.14`
- three currencies
- 25 amount buckets
- debtor and creditor identities
- execution or settlement dates
- message-dependent payment attributes

The XSDs carry ISO Standards Editor provenance. The official ISO download host was attempted first but did not respond from the GitHub runner. Commit-pinned public copies were used and their exact hashes and source URLs are recorded under `provenance/`.

### Results

- **800 valid documents generated**
- **800 accepted by lxml/libxml2**
- **800 accepted by xmlschema 4.3.2**
- **800 decoded and semantically checked**
- **0 validator disagreements**
- **0 valid-document failures**

Five controlled invalid transformations were applied to 200 documents, producing **1,000 invalid documents**. Both independent validators rejected all 1,000.

The evaluation demonstrates that PDRS can drive standards-derived financial-message validation while retaining a compact exact reproducer for each message.

## Large-campaign coordination stress test

Generation-only stress tests quantify when duplicate-free rank addressing becomes operationally useful.

### Duplicate draws at 500,000 cases

| Domain | Random replacement duplicates | PDRS without replacement |
|---|---:|---:|
| SimpleFIX, 719.3 million objects | 192 | 0 |
| QuantLib, 3.36 million objects | 35,604 | 0 |
| ISO 20022, 4.32 million objects | 28,031 | 0 |

### Eight workers with 50,000 unique draws each

| Domain | Independent random cross-worker overlap | PDRS interval overlap |
|---|---:|---:|
| SimpleFIX | 98 | 0 |
| QuantLib | 20,078 | 0 |
| ISO 20022 | 15,828 | 0 |

For the QuantLib domain, independent workers lost about **5.06%** of their combined unique work to overlap. For ISO 20022, the loss was about **3.98%**. PDRS partitions were disjoint by construction.

## What the evaluation proves

The evidence supports these claims for the declared finite bounded profiles:

1. PDRS can generate valid inputs for real finance packages and standards, not only synthetic examples.
2. Schema hash plus rank gives an exact and compact reproducer for every scenario or message.
3. No-replacement generation and interval sharding eliminate duplicate scenarios and cross-worker overlap.
4. PDRS integrates naturally with parser oracles, independent numerical formulas, metamorphic relations, differential engines, and independent XSD validators.
5. Native program execution usually dominates PDRS generation cost in these workloads.

## What it does not prove

1. PDRS does not universally improve code coverage. SimpleFIX coverage was equal across the tested methods.
2. Object-uniform sampling may under-sample small top-level branches. Weighted or stratified PDRS sampling is a valuable next extension.
3. No previously unknown SimpleFIX, QuantLib, or ISO-schema defect was confirmed in this campaign.
4. PDRS does not make QuantLib's pricing algorithms intrinsically faster.
5. The ISO 20022 profiles are deliberately bounded finite subsets, not unrestricted generation of every value permitted by the full standards.
6. Timing values are specific to the recorded hosted-runner environment.

## Research significance

The campaign validates PDRS's strongest practical role: **rank-addressable orchestration of large finite test and scenario spaces**. Its value rises when campaigns are large, expensive per case, distributed across workers, or require exact reproducibility and completion accounting. It is less compelling when the domain is small, duplicate probability is negligible, or local branch balance is more important than object-level uniformity.
