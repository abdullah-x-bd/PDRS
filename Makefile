.PHONY: test check benchmark all

test:
	PYTHONPATH=src python -m unittest discover -s tests -v

check:
	python scripts/check_research_assets.py

benchmark:
	python scripts/run_benchmarks.py --output results/baseline_density.csv

all: test check benchmark
