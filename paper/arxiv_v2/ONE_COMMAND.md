# One-command reproduction

`make reproduce` is the authoritative synthetic-paper command. It runs unit tests, regenerates raw evidence, recomputes paired intervals, recreates figures, compiles the manuscript, and fails on LaTeX overflow. The external finance workflow remains separate because its dependencies and XSD retrieval require a networked CI environment.
