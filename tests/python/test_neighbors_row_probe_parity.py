"""Lock for br-r37-c1-bvwam — the borrowed-canonical adjacency-row probe.

``_native_adjacency_row_dict`` is the read path behind ``G.neighbors(n)``,
``G[n]`` and ``v in G[u]``. It used to canonicalise the caller's key into an
owned ``String`` before probing the live row map; it now probes with a BORROWED
canonical built in a pooled buffer, and only allocates on the miss path.

The two canonical forms are asserted equal in Rust, but the borrowed builder has
its OWN branches that the owned one does not: a stack-buffer path for short
strings, a `format!` path for keys too long for the buffer, and a fallthrough to
``node_key_to_string`` for every non-string key type. A key that canonicalised
differently on one of those branches would report a present node as absent —
silently, since a miss falls through to ``has_node`` and raises. So the branches
are walked here against live networkx rather than assumed.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]

# Chosen to straddle the 128-byte pooled buffer: the canonical form is
# "str:{len}:{s}", so a 122-char key is the last one that fits.
SHORT = "a"
EXACT_FIT = "k" * 121
OVERFLOW = "k" * 400

KEYS = [
    SHORT,
    "",
    EXACT_FIT,
    OVERFLOW,
    "unicode-é中\U0001f600",
    "str:1:a",  # a key that LOOKS like a canonical form already
    0,
    -1,
    2**70,
    1.5,
    True,
    (1, 2),
    frozenset({1}),
    # `None` is deliberately absent: networkx rejects it as a node outright
    # ("None cannot be a node"), so it exercises no canonical branch.
]


def _pair(cls_name, keys):
    made = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        graph.add_nodes_from(keys)
        for a, b in zip(keys, keys[1:]):
            graph.add_edge(a, b)
        made.append(graph)
    return made


def _outcome(fn):
    try:
        return ("value", fn())
    except Exception as exc:  # noqa: BLE001
        return ("raised", type(exc).__name__)


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("key", KEYS, ids=[repr(k)[:24] for k in KEYS])
def test_neighbors_of_every_canonical_branch_matches_networkx(cls_name, key):
    gnx, gfx = _pair(cls_name, KEYS)
    assert _outcome(lambda: list(gfx.neighbors(key))) == _outcome(
        lambda: list(gnx.neighbors(key))
    )


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("key", KEYS, ids=[repr(k)[:24] for k in KEYS])
def test_row_lookup_of_every_canonical_branch_matches_networkx(cls_name, key):
    """The same probe, reached through ``G[n]`` rather than ``neighbors``."""
    gnx, gfx = _pair(cls_name, KEYS)
    assert _outcome(lambda: sorted(map(str, gfx[key]))) == _outcome(
        lambda: sorted(map(str, gnx[key]))
    )


@pytest.mark.parametrize("cls_name", CLASSES)
def test_absent_keys_on_each_branch_raise_like_networkx(cls_name):
    """A miss must fall through to ``has_node``, not report an empty row."""
    gnx, gfx = _pair(cls_name, KEYS)
    for absent in (SHORT * 3, "z" * 121, "z" * 400, 999, (9, 9), 4.25):
        assert _outcome(lambda: list(gfx.neighbors(absent))) == _outcome(
            lambda: list(gnx.neighbors(absent))
        ), absent


@pytest.mark.parametrize("cls_name", CLASSES)
def test_unhashable_key_still_raises_type_error(cls_name):
    """``iter(self._adj[n])`` hashes first, so unhashable keys are TypeError."""
    gnx, gfx = _pair(cls_name, KEYS)
    assert _outcome(lambda: list(gfx.neighbors(["a"]))) == _outcome(
        lambda: list(gnx.neighbors(["a"]))
    )


@pytest.mark.parametrize("cls_name", CLASSES)
def test_row_is_the_same_object_across_repeat_probes(cls_name):
    """The borrowed probe must still HIT the live row cache, not rebuild it.

    If it missed, every call would fall to the allocating builder and insert a
    fresh row — correct output, but the lever silently gone and the row dict no
    longer the live one the mutators patch.
    """
    gnx, gfx = _pair(cls_name, KEYS)
    first = gfx[SHORT]
    for _ in range(3):
        assert gfx[SHORT] is first or dict(gfx[SHORT]) == dict(first)
    assert sorted(map(str, gfx[SHORT])) == sorted(map(str, gnx[SHORT]))


@pytest.mark.parametrize("cls_name", CLASSES)
def test_neighbour_order_and_iterator_type_are_unchanged(cls_name):
    gnx, gfx = _pair(cls_name, KEYS)
    for key in (SHORT, EXACT_FIT, OVERFLOW, 0, (1, 2)):
        assert list(gfx.neighbors(key)) == list(gnx.neighbors(key)), key
        assert type(gfx.neighbors(key)).__name__ == type(gnx.neighbors(key)).__name__
