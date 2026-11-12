"""The public read API under ASSIGNED private storage must match networkx.

br-r37-c1-vbe1o. networkx lets a caller assign the private mappings directly -
``G._adj = {...}``, ``G._succ``, ``G._pred``, ``G._node`` - and every public read is
expected to answer from what was assigned. fnx keeps a native store alongside, so an
assignment that carries a node the native store does not have is the case where the two
can disagree.

WHY THIS IS A TEST AND NOT ONLY A DIAGNOSTIC. scripts/probe_private_storage_parity.py
swept this surface and found 97 divergences out of 368 comparisons when it landed, in
groups the bead ranked by severity - silent wrong booleans (``G.has_edge('ZZ','b')``
answering False where networkx answers True), wrong return types (``G.degree('ZZ')``
handing back a view where networkx returns an int, so a caller doing arithmetic gets a
TypeError), wrong node sets in both directions, and accessors raising where networkx
returns. It was deliberately written as a reporting tool "so it stays useful while the
family is being worked through".

That family is now closed. The same sweep reports 0 of 368 on HEAD, so the surface is
asserted here rather than only reported, and the 97 cannot come back silently.

THE GUARD HAS BEEN SEEN TO FAIL, which is the only thing that makes it worth having.
Against the package's ``__init__.py`` as of b873d30c2 - the commit that introduced the
probe - with the current native extension, 97 of these 368 assertions fail. On HEAD, 0 do.

VALIDATING IT AGAINST ANOTHER ARM CANNOT BE DONE UNDER PYTEST, and the attempt returns a
false green. ``tests/python/conftest.py`` inserts the repo ``python/`` directory at
``sys.path[0]``, which wins over ``PYTHONPATH``, so pointing ``PYTHONPATH`` at an
alternative package tree and running pytest silently keeps testing the repo copy - it
reported 369 passed against the arm that has 97 real divergences. Drive the sweep from
plain ``python3`` (importing ``probe_private_storage_parity`` and calling
``compare_one``) when checking a guard against a different arm.

The case table lives in the probe module and is imported rather than copied, so the
diagnostic and this lock cannot drift apart. Exceptions are compared by type AND args,
because a type-only sweep reports false green.
"""

import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import probe_private_storage_parity as probe  # noqa: E402

_CELLS = list(probe.iter_cells())


def test_the_sweep_still_covers_the_whole_surface():
    """A shrunken sweep would make every row below pass for the wrong reason."""
    assert len(_CELLS) == 368, f"expected 368 comparisons, got {len(_CELLS)}"


@pytest.mark.parametrize(
    ("cls", "attr", "mapping", "fn"),
    [pytest.param(c, a, m, f, id=f"{c}-{a}-{label}") for c, a, m, label, f in _CELLS],
)
def test_assigned_private_storage_read_matches_networkx(cls, attr, mapping, fn):
    expected, got = probe.compare_one(cls, attr, mapping, fn)
    assert got == expected
