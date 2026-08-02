# Reproducibility

The deterministic artifact can be reproduced with:

```bash
make all
```

The command runs tests, validates research assets, and regenerates `results/baseline_density.csv`.

Every future hardware-dependent experiment must record:

- Git commit
- schema and dataset hashes
- random seed
- operating system
- language and dependency versions
- CPU, memory, and core count
- exact command
- raw output paths

Deterministic generated outputs must be checked by CI. Hardware-dependent outputs should be stored with manifests and should not be compared byte-for-byte across machines.
