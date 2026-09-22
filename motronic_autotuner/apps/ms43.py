"""Siemens MS43 tuner: ``python -m motronic_autotuner.apps.ms43`` or the ``motronic-ms43`` script."""

from __future__ import annotations

import sys


def main() -> int:
    from ..families.siemens_ms43 import SIEMENS_MS43
    from ..gui.app import run

    return run(SIEMENS_MS43)


if __name__ == "__main__":
    sys.exit(main())
