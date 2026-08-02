# Contributing

All changes should advance a registered claim, experiment, counterexample, or reproducibility requirement.

## Pull request requirements

A pull request should state:

1. the claim or issue it addresses
2. the files and assumptions changed
3. tests or experiments executed
4. new limitations or negative findings
5. paper sections affected

Run before submission:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
python scripts/run_benchmarks.py --output /tmp/pdrs-density.csv
python scripts/check_research_assets.py
```

Do not manually edit generated result tables without updating the generating script and experiment manifest.
