"""Bosch ME7 tuner: ``python -m motronic_autotuner.apps.me7`` or the ``motronic-me7`` script."""

from __future__ import annotations

import sys


def main() -> int:
    from ..families.bosch_me7 import BOSCH_ME7
    from ..gui.app import run

    return run(BOSCH_ME7)


if __name__ == "__main__":
    sys.exit(main())
