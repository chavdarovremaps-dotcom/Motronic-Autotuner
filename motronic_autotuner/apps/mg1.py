"""Bosch MG1CS201 tuner: ``python -m motronic_autotuner.apps.mg1`` or the ``motronic-mg1`` script."""

from __future__ import annotations

import sys


def main() -> int:
    from ..families.bosch_mg1cs201 import BOSCH_MG1CS201
    from ..gui.app import run

    return run(BOSCH_MG1CS201)


if __name__ == "__main__":
    sys.exit(main())
