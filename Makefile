.PHONY: test proof corpus evidence-quick evidence-full derive verify all

corpus:
	PYTHONPATH=src python scripts/build_corpus.py

test:
	PYTHONPATH=src python -m unittest discover -s tests -v

proof:
	PYTHONPATH=src python scripts/verify_theorems.py --schemas 1000

evidence-quick:
	@for stage in correctness density runtime uniformity fuzzing schema_evolution fault_propagation scalability_and_timing crypto_adapter; do \
		PYTHONPATH=src python scripts/run_full_experiments.py --stage $$stage --quick || exit 1; \
	done
	PYTHONPATH=src python scripts/derive_tables.py
	python scripts/assemble_evidence.py

evidence-full:
	@for stage in correctness density runtime uniformity fuzzing schema_evolution fault_propagation scalability_and_timing crypto_adapter; do \
		PYTHONPATH=src python scripts/run_full_experiments.py --stage $$stage || exit 1; \
	done
	PYTHONPATH=src python scripts/derive_tables.py
	python scripts/assemble_evidence.py

derive:
	PYTHONPATH=src python scripts/derive_tables.py
	python scripts/assemble_evidence.py

verify:
	python scripts/verify_evidence.py

all: corpus test proof evidence-quick verify
