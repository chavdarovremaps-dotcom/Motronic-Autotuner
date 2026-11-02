"""Siemens MS43X turbo tuner: python -m motronic_autotuner.apps.ms43_turbo, or the motronic-ms43-turbo script."""

from __future__ import annotations

import sys


def main() -> int:
    from ..gui.app import run
    from ..ms43_turbo.family import MS43_TURBO

    return run(MS43_TURBO)


if __name__ == "__main__":
    sys.exit(main())
