"""Bosch ME7.6.2 Opel tuner on vehicle-logger CSVs:
``python -m motronic_autotuner.apps.me762_vehicle`` or the ``motronic-me762-vehicle`` script."""

from __future__ import annotations

import sys


def main() -> int:
    from ..families.bosch_me762 import BOSCH_ME762
    from ..gui.app import run

    return run(BOSCH_ME762)


if __name__ == "__main__":
    sys.exit(main())
