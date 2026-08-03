# PDRS arXiv evidence freeze

This revision separates software releases from evidence commits.

| Component | Immutable identity | Public version | Role |
|---|---|---|---|
| PDRS base | `272602cc41bc75b37e54f4d0cefb7af603419c1c` | `pdrs==0.2.0` | Compiler, runtimes, evidence v1 |
| FinSpace base | `3760f1480e3ef19e4ff0928ddd6938e04045ab1b` | `finspace==0.1.0` | Finance application layer |
| SOTA evidence v1 | `d05fa968ed555e4858b2f4d2164387f01d605d8e` | n/a | Six-system matched campaign |
| Real-program evidence v1 | `08c58bc9c6ae6cd067f06027f4ad30370f6dc6c8` | n/a | SimpleFIX, QuantLib, ISO 20022 |
| Native evidence v1 | `fe92c2563bd5b2a7da931d66a9beda1d42d04aa2` | n/a | C and Rust conformance and timing |

The arXiv-v2 branch adds evidence v2 without altering historical evidence v1. Every regenerated file is produced from scripts in the complete source-and-evidence archive. The final revision will receive an immutable paper tag after review. A Zenodo DOI requires an authenticated repository release and remains a repository-owner action.
