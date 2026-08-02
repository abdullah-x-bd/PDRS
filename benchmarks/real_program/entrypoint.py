"""Fair and complete real-program evaluation entry point.

SimpleFIX is imported before coverage starts so every compared generation method
measures runtime package coverage under the same already-imported module state.
The large-campaign coordination stress test runs first so the main orchestrator's
final checksum manifest includes its data and figures.
"""

import simplefix  # noqa: F401  Preload before coverage measurement.

from .scale import run as run_scale
from .run_all import main


if __name__ == "__main__":
    run_scale()
    main()
