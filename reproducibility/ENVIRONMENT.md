# Reproducibility environment

The reference code requires Python 3.11 or newer. Experiment plotting and analysis require packages listed in `requirements-experiments.txt`.

The committed performance run records its exact interpreter and host metadata in `results/raw/runtime_environment.json`. Correctness, density, uniformity, fuzzing, evolution, fault, and cryptographic test data are seed-controlled. Runtime and micro-timing values will differ across machines.

For a clean reproduction:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python -m pip install -r requirements-experiments.txt
make test
make proof
make evidence-full
make verify
```
