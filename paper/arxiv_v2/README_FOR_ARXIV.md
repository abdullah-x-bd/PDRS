# arXiv source upload

Upload the contents of `paper/` together with the generated PDF figures from `figures/`. The source uses standard TeX Live packages and BibTeX. Compile with:

```bash
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

Before upload, replace the DOI placeholder only after Zenodo has minted an actual DOI and rerun the complete build. Do not upload generated auxiliary files.
