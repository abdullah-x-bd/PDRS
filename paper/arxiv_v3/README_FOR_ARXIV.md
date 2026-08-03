# arXiv source instructions

Upload `main.tex`, `references.bib`, `generated_macros.tex`, `generated_tables.tex`, the `sections/` and `appendices/` directories, and all thirteen generated PDF figures in one source archive.

Compile with:

```bash
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

Do not add a DOI until Zenodo has archived an immutable GitHub release and the DOI resolves to that exact release. Review the author block before submission.
