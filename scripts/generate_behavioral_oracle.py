#!/usr/bin/env python3
"""Checkout launcher for the authoritative packaged behavioral oracle."""

from pathlib import Path
from runpy import run_path


_source = (
    Path(__file__).resolve().parents[1]
    / "crates"
    / "fnx-conformance"
    / "src"
    / "behavioral_oracle.py"
)

if __name__ == "__main__":
    run_path(str(_source), run_name="__main__")
else:
    globals().update(run_path(str(_source), run_name=__name__))
