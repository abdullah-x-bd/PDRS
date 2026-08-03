# arXiv v2 reproducibility

## Frozen source identities

The revision uses these immutable source references:

- PDRS evidence source: `a2f0449c254f8d222a7fcb62b34367ec532ce7a9`
- FinSpace source: `3760f1480e3ef19e4ff0928ddd6938e04045ab1b`
- Published packages: `pdrs==0.2.0` and `finspace==0.1.0`

The PDRS README used the phrase “Version 0.3 evidence” for repository functionality that was not released as a separate PyPI 0.3 distribution. The manuscript therefore identifies evaluated source by commit SHA and reports the PyPI package version separately.

## One-command synthetic reproduction

From this directory:

```bash
python -m pip install -r requirements-lock.txt
make reproduce
```

The command runs the semantic tests, regenerates all Phase 1–8 raw observations, computes the paired bootstrap analysis, creates the figures, compiles the paper, and fails on an overfull LaTeX box.

Container reproduction:

```bash
docker build -t pdrs-arxiv-v2 .
docker run --rm pdrs-arxiv-v2
```

## Evidence levels

- `results/` under this directory contains the redesigned synthetic and orchestration evidence.
- The repository’s existing `results/sota` and `results/real_program` directories remain the frozen first evidence layer.
- `results/real_program_v2` is generated only by the external dependency workflow. It never overwrites the first evidence layer.

## Statistical unit

One complete seeded campaign is the independent experimental unit. Budget prefixes remain nested observations and are never presented as independent replicates. The analysis pairs methods within repetition, distribution, and budget, then bootstraps complete paired campaigns.

## Checksums

`SHA256SUMS.csv` is generated from every file in the arXiv v2 directory except the checksum file itself. GitHub Actions archives the generated checksum manifest with the evidence.

## Permanent archive

A permanent Zenodo DOI requires the repository owner to connect GitHub to Zenodo, enable this repository, and create an immutable GitHub release. The artifact leaves the DOI field empty until Zenodo returns an actual DOI. The paper must not cite a placeholder DOI.
