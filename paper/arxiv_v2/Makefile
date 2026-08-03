.PHONY: install test evidence paper reproduce clean

PYTHON ?= python

install:
	$(PYTHON) -m pip install -r requirements-lock.txt

test:
	$(PYTHON) -m unittest discover -s tests -v

evidence:
	$(PYTHON) experiments/run_phase1_9.py

paper: evidence
	cd paper && pdflatex -interaction=nonstopmode -halt-on-error main.tex
	cd paper && bibtex main
	cd paper && pdflatex -interaction=nonstopmode -halt-on-error main.tex
	cd paper && pdflatex -interaction=nonstopmode -halt-on-error main.tex
	! grep -q "Overfull \\hbox" paper/main.log

reproduce: test paper

clean:
	rm -rf results/raw results/processed figures/*.pdf
	rm -f paper/main.aux paper/main.bbl paper/main.blg paper/main.log paper/main.out paper/main.pdf
