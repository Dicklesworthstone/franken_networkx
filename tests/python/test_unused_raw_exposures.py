"""br-r37-c1-fmggo: gate on every unused _raw_<X> exposure being
triaged.

The triage in scripts/find_unused_raw_exposures.py classifies each
_raw_<X> binding that has only an import-line reference in
__init__.py. If a new _raw_<X> is added without a TRIAGE entry, this
test fails — forcing the author to think about whether the binding
should be kept (direct-Rust API), wired up (perf win), or removed
(dead code).
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import franken_networkx as fnx


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO_ROOT / "scripts" / "find_unused_raw_exposures.py"


def _load_triage() -> dict:
    spec = importlib.util.spec_from_file_location("find_unused", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["find_unused"] = module
    spec.loader.exec_module(module)
    return module.TRIAGE


def _find_unused_raw() -> list[str]:
    init_path = REPO_ROOT / "python" / "franken_networkx" / "__init__.py"
    text = init_path.read_text(encoding="utf-8")
    return [
        n
        for n in dir(fnx)
        if n.startswith("_raw_")
        and len(re.findall(rf"\b{re.escape(n)}\b", text)) <= 1
    ]


def test_every_unused_raw_has_triage_entry():
    """If a _raw_<X> binding goes unused, force a documented decision
    about whether to keep / wire / remove it."""
    unused = _find_unused_raw()
    triage = _load_triage()
    untriaged = [n for n in unused if n not in triage]
    assert not untriaged, (
        "New _raw_<X> exposures without triage entries:\n  - "
        + "\n  - ".join(untriaged)
        + "\nAdd them to scripts/find_unused_raw_exposures.py::TRIAGE."
    )


def test_triage_decisions_are_well_formed():
    """Every triage entry must use one of the canonical decision
    categories so the report renders correctly."""
    triage = _load_triage()
    valid = {"keep-public-api", "wire-up", "remove"}
    for name, (decision, rationale) in triage.items():
        assert decision in valid, f"{name}: unknown decision {decision!r}"
        assert rationale.strip(), f"{name}: empty rationale"
