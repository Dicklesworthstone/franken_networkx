"""The A/B harness must refuse to measure a DEBUG extension.

br-r37-c1-debugso. `maturin develop` without `--release` installs a debug build
into the shared venv, and on 2026-08-24 one sat there while several panes
measured against it. The effect is not subtle and it does not announce itself:

    G.edges[u,v] against live networkx, same tree, same op
        debug   .so   1733.6 ns   0.07x
        release .so    185.0 ns   0.69x        9.4x apart

A trivial `len(G)` reads 252ns on debug and 43.5ns on release, so every ratio
taken against a debug build is wrong by roughly the boundary cost - and wrong in
the direction that INVENTS Python-Rust crossing losses. That is the expensive
part: one such number was attributed to a real mechanism, fixed, measured as a 9x
win, and the fix reverted only after the same probes were re-run on a release
build (5457e5af1). The harness now refuses instead.

WHY `--expect-elf` DOES NOT COVER THIS, which is the whole reason for a second
guard: it compares the loaded sha against the one you INTENDED to measure, so it
catches a binary swapped mid-run and is silent about a debug binary that was
already installed when the run started. The two guards answer different
questions.
"""

from __future__ import annotations

import hashlib
import importlib.util
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
HARNESS = ROOT / "scripts" / "balanced_square_ab.py"


def _harness_module():
    spec = importlib.util.spec_from_file_location("_bsab_under_test", HARNESS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def harness():
    if not HARNESS.exists():
        pytest.skip("balanced_square_ab.py is not present")
    return _harness_module()


def _artifact(profile):
    path = ROOT / "target" / profile / "lib_fnx.so"
    if not path.exists():
        pytest.skip(f"no {profile} artifact built in this tree")
    with open(path, "rb") as handle:
        return str(path), hashlib.sha256(handle.read()).hexdigest()


@pytest.mark.parametrize("profile", ["release", "debug"])
def test_the_profile_of_a_cargo_artifact_is_identified_exactly(harness, profile):
    """Identified by sha against cargo's own output, not guessed from size.

    Size alone would be a heuristic; an exact match against
    `target/<profile>/lib_fnx.so` is proof, and it is what lets the harness say
    "debug" rather than "large".
    """
    path, sha = _artifact(profile)

    assert harness._installed_build_profile(path, sha) == profile


def test_an_unknown_binary_is_not_called_debug_on_size_alone(harness, tmp_path):
    """A small unmatched file is `unknown`, never a false debug accusation.

    The refusal is a wall in front of every measurement, so it must not fire on a
    wheel install or a tree built elsewhere. Only a genuine size outlier - the
    two profiles differ by more than 10x - falls back to a guess.
    """
    stranger = tmp_path / "_fnx.abi3.so"
    stranger.write_bytes(b"not an extension")
    sha = hashlib.sha256(stranger.read_bytes()).hexdigest()

    assert harness._installed_build_profile(str(stranger), sha) == "unknown"


def test_a_missing_file_does_not_raise(harness):
    """The helper runs inside provenance(); it must degrade, not explode."""
    assert harness._installed_build_profile("/nonexistent/_fnx.abi3.so", "0" * 64) in (
        "unknown",
        "probably-debug",
    )


def test_the_refusal_names_the_command_that_fixes_it(harness):
    """A guard that does not say what to do next just moves the confusion.

    The message has to carry the exact build line, because the marching orders
    circulating in this project omit `--release` and that is how the debug build
    keeps getting installed.
    """
    source = HARNESS.read_text()

    assert "DEBUG EXTENSION" in source
    assert "maturin develop --release" in source
    assert "--measure-debug-build-anyway" in source


def test_the_profile_is_reported_in_provenance(harness):
    """Every run prints it, so a banked row records which profile produced it."""
    provenance = harness.provenance()

    assert "build_profile" in provenance
    assert provenance["build_profile"] in (
        "release",
        "debug",
        "probably-debug",
        "unknown",
    )
