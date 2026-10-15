"""Bosch ME1.5.5 Opel tuner on vehicle-logger CSVs:
``python -m motronic_autotuner.apps.me155_vehicle`` or the ``motronic-me155-vehicle`` script."""

from __future__ import annotations

import sys


def main() -> int:
    from ..families.bosch_me155 import BOSCH_ME155
    from ..gui.app import run

    return run(BOSCH_ME155)


if __name__ == "__main__":
    sys.exit(main())
