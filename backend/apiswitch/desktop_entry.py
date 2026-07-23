"""Executable entrypoint for normal desktop startup and packaged diagnostics."""

from __future__ import annotations

import sys

from apiswitch.desktop import run_desktop
from apiswitch.desktop_diagnostics import run_diagnostics_from_args


def main() -> None:
    diagnostic_exit_code = run_diagnostics_from_args(sys.argv[1:])
    if diagnostic_exit_code is not None:
        raise SystemExit(diagnostic_exit_code)
    run_desktop(start_hidden="--background" in sys.argv[1:])


if __name__ == "__main__":
    main()
