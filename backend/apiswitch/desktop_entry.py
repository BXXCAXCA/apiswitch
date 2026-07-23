"""Executable entrypoint for normal desktop startup and packaged diagnostics."""

from __future__ import annotations

import os
import sys
from typing import TextIO

from apiswitch.desktop import run_desktop
from apiswitch.desktop_diagnostics import run_diagnostics_from_args

_DEVNULL_STREAMS: list[TextIO] = []


def _ensure_standard_streams() -> None:
    """Provide sinks required by logging libraries in PyInstaller windowed mode."""
    for name in ("stdout", "stderr"):
        if getattr(sys, name) is not None:
            continue
        stream = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
        _DEVNULL_STREAMS.append(stream)
        setattr(sys, name, stream)


def main() -> None:
    _ensure_standard_streams()
    diagnostic_exit_code = run_diagnostics_from_args(sys.argv[1:])
    if diagnostic_exit_code is not None:
        raise SystemExit(diagnostic_exit_code)
    run_desktop(start_hidden="--background" in sys.argv[1:])


if __name__ == "__main__":
    main()
