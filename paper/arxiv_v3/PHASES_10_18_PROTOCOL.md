# Phase 10–18 protocol

This protocol fixes the evaluation before the final CI run.

## Phase 10: representation and integrity

Five finite dependent schemas are evaluated. The experiment separates fixed-width schema-relative identity, expected variable-length payload under four declared distributions, and self-contained messages with framing, canonicalization version, a 128-bit schema identifier, rank length, rank bytes, and optional CRC-32 or 128-bit HMAC. Block sizes are 1, 16, 256, and 4,096.

Baselines are enumerative indexing, local mixed radix, an independent PER-style calculation, actual ASN.1 UPER and aligned PER through `asn1tools`, arithmetic ideal lengths with termination overhead, rANS ideal lengths with explicit table and state overhead, a reduced MDD index, an external BDD model count, schema-specific packing, MessagePack, and canonical JSON. Unsupported translations are recorded rather than scored as losses.

Corruption classes are single-bit, two-bit, burst, random-byte replacement, and truncation. The raw-rank experiment reports how often a changed rank remains in the valid interval. Checksums test accidental corruption. HMAC tests integrity and authenticity under the declared key model.

## Phase 11: semantic and implementation validation

The independent recursive oracle shares no PDRS count, prefix, rank, or unrank code. Exact-set comparison covers the permit and imbalanced domains exhaustively. The malformed corpus contains 13 curated documents and 1,000 deterministic malformed documents. The canonicalization matrix covers Boolean/integer distinction, signed zero, NaN, Unicode normalization, decimals, dates, duplicate JSON keys, mapping order, branch order, and infinity.

Python receives 18 curated semantic mutants. The last six are held out from the ordinary suite. C and Rust receive the arithmetic, boundary, and overflow subset applicable to runtimes that consume validated canonical IR. Build-invalid and non-applicable mutants are reported separately.

## Phase 12: replay

Object identity contains canonicalization version, schema identity, rank, PDRS version, and optional commit. Execution identity additionally binds FinSpace, adapter, environment, oracle, execution parameters, external data, and result. Object reconstruction and execution-result reproduction use separate verification states.

## Phases 13–17: paper, figures, and language

The manuscript is organized by research question. Thirteen vector figures regenerate from raw evidence. Numerical claims come from generated macros or the claim ledger. An affirmative promotional-claim audit fails CI. Direct limitations remain in the main text.

## Phase 18: stopping rule

The technical scorecard passes only when every executable check succeeds. A held-out mutation score satisfies the final defect-evidence alternative; no synthetic mutant is described as a historical defect. The permanent-archive row remains pending until Zenodo actually mints a resolving DOI for an immutable release. No placeholder DOI is allowed.
