"""Fair real-program entry point.

SimpleFIX is imported before coverage starts so every compared generation method
measures runtime package coverage under the same already-imported module state.
This prevents the first method from receiving one-time import-line credit.
"""

import simplefix  # noqa: F401  Preload before coverage measurement.

from .run_all import main


if __name__ == "__main__":
    main()
