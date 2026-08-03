.PHONY: assemble test evidence external rust finalize paper reproduce reproduce-full clean
PYTHON ?= python
BIBTEX ?= bibtex

assemble:
	$(PYTHON) assemble_sources.py

test: assemble
	$(PYTHON) -m unittest discover -s tests -v

evidence: assemble
	$(PYTHON) experiments/run_all.py

external: assemble
	$(PYTHON) experiments/external_baselines.py

rust:
	$(PYTHON) experiments/run_rust_mutants.py

finalize:
	$(PYTHON) experiments/finalize_phase_10_18.py

paper:
	cd paper && pdflatex -interaction=nonstopmode -halt-on-error main.tex
	cd paper && $(BIBTEX) main
	cd paper && pdflatex -interaction=nonstopmode -halt-on-error main.tex
	cd paper && pdflatex -interaction=nonstopmode -halt-on-error main.tex
	! grep -q "Overfull \\hbox" paper/main.log

reproduce: test evidence
	$(PYTHON) paper/generate_results_tex.py
	$(MAKE) paper

reproduce-full: test evidence external rust finalize paper

clean:
	rm -rf results/raw/* results/processed/* figures/*
	rm -f src/model.py experiments/run_all.py
	rm -f paper/*.aux paper/*.bbl paper/*.blg paper/*.log paper/*.out paper/*.pdf
