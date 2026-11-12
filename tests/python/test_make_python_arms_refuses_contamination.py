"""The arm builder must REFUSE the pair that cost two retracted ledger rows.

br-r37-c1-aeshim. I built one arm from ``git show HEAD:...`` and the other by
copying the working tree; a peer commit landed between those two acts and my
arms differed by my five-line change plus their entire commit. Nothing looked
wrong - both arms imported, both parity-gated, and the resulting test failure was
perfectly DETERMINISTIC, which felt like proof of causation and was only proof
that the arms differed.

``scripts/make_python_arms.py`` exists so the safe procedure is the cheap one. It
is only worth having if its REFUSALS hold, so those are what this file tests: a
builder that silently produced a contaminated pair would be worse than no builder
at all, because it would carry authority.
"""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "make_python_arms.py"


@pytest.fixture()
def builder():
    spec = importlib.util.spec_from_file_location("arms_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_aa_pair_is_clean(builder, tmp_path):
    assert builder.build_arms(tmp_path / "aa", None, "__init__.py") == 0
    a = tmp_path / "aa" / "armA" / "franken_networkx" / "__init__.py"
    b = tmp_path / "aa" / "armB" / "franken_networkx" / "__init__.py"
    assert a.read_bytes() == b.read_bytes()


def test_ab_pair_with_a_patch_is_accepted(builder, tmp_path):
    patched = tmp_path / "patched.py"
    src = (REPO / "python" / "franken_networkx" / "__init__.py").read_text()
    patched.write_text(src + "\n# a one-line difference\n")
    assert builder.build_arms(tmp_path / "ab", patched, "__init__.py") == 0


def test_reused_outdir_is_refused(builder, tmp_path):
    """THE failure mode: reusing a directory silently mixes two tree states."""
    out = tmp_path / "reused"
    assert builder.build_arms(out, None, "__init__.py") == 0
    assert builder.build_arms(out, None, "__init__.py") == 2


def test_patching_a_file_outside_the_package_is_refused(builder, tmp_path):
    patched = tmp_path / "p.py"
    patched.write_text("x = 1\n")
    assert builder.build_arms(tmp_path / "bad", patched, "no_such_file.py") == 2


def test_arms_are_copied_not_referenced(builder, tmp_path):
    """Arms must be independent: editing one cannot reach the other or the repo."""
    out = tmp_path / "indep"
    assert builder.build_arms(out, None, "__init__.py") == 0
    a = out / "armA" / "franken_networkx" / "__init__.py"
    before_b = (out / "armB" / "franken_networkx" / "__init__.py").read_bytes()
    before_repo = (REPO / "python" / "franken_networkx" / "__init__.py").read_bytes()
    a.write_text(a.read_text() + "\n# mutate arm A only\n")
    assert (out / "armB" / "franken_networkx" / "__init__.py").read_bytes() == before_b
    assert (REPO / "python" / "franken_networkx" / "__init__.py").read_bytes() == before_repo


def test_staleness_check_uses_the_same_rule_as_conftest(builder):
    """If this drifts from conftest's rule, the warning stops meaning anything."""
    source = SCRIPT.read_text()
    assert "_fnx.abi3.so" in source
    assert "crates" in source.lower()
    stale, _delta = builder.binary_is_stale()
    assert isinstance(stale, bool)


def test_shared_elf_is_asserted(builder):
    """A Python-arm comparison whose arms differ in the BINARY measures two things."""
    body = SCRIPT.read_text().split("def build_arms", 1)[1]
    assert "do not share an ELF" in body, (
        "build_arms must refuse arms whose _fnx.abi3.so differs"
    )
