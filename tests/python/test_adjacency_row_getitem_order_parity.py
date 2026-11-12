"""Lock for br-r37-c1-i7jta — the cache-first `G.adj[u]` row lookup.

`MultiAdjacencyView.__getitem__` used to run an explicit ``hash(node)``, a full
``node not in owner`` graph-membership probe and a ``getattr`` for the native row
binding BEFORE probing the per-row cache that already held the answer. Those now
sit behind the cache probe, justified by the cached row being existence proof
under an unchanged ``nodes_seq``.

That reorder can only be wrong in specific ways, and each one is pinned here:

* an UNHASHABLE key must still raise TypeError. On the warm path nothing calls
  ``hash`` explicitly any more — ``dict.get`` is what raises — so the contract
  now depends on a fast path that a cold graph never reaches. Both states are
  tested.
* a MISSING node must still raise KeyError with networkx's key, not be answered
  from a stale cache entry.
* a node REMOVED after its row was cached must stop resolving. This is the
  existence-proof assumption stated as a test: it holds only because removal
  bumps ``nodes_seq``.
* the br-r37-c1-ka7fd contract — an assigned ``G._node`` must not hide a node
  that has a real adjacency row — must survive, INCLUDING when the row was
  cached before the assignment, since assigning ``_node`` does not bump
  ``nodes_seq``.
* a captured row must still see later EDGE churn, which is what makes caching it
  across edge mutations legal in the first place.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _pair(cls_name):
    made = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        graph.add_edges_from([("a", "b"), ("a", "c"), ("b", "c")])
        made.append(graph)
    return made


def _outcome(fn):
    try:
        return ("value", fn())
    except Exception as exc:  # noqa: BLE001
        return ("raised", type(exc).__name__, str(exc))


@pytest.mark.parametrize("cls_name", CLASSES)
def test_unhashable_key_raises_type_error_cold_and_warm(cls_name):
    """The warm path relies on ``dict.get`` to hash; the cold path on ``hash``."""
    gnx, gfx = _pair(cls_name)
    cold = _outcome(lambda: gfx.adj[["a"]])
    assert cold == _outcome(lambda: gnx.adj[["a"]])
    assert cold[0] == "raised" and cold[1] == "TypeError"

    gfx.adj["a"]  # populate the per-row cache
    gnx.adj["a"]
    warm = _outcome(lambda: gfx.adj[["a"]])
    assert warm == _outcome(lambda: gnx.adj[["a"]])
    assert warm[1] == "TypeError", "warm path stopped hashing the key"


@pytest.mark.parametrize("cls_name", CLASSES)
def test_missing_node_raises_like_networkx_cold_and_warm(cls_name):
    gnx, gfx = _pair(cls_name)
    assert _outcome(lambda: gfx.adj["zz"]) == _outcome(lambda: gnx.adj["zz"])
    gfx.adj["a"]
    gnx.adj["a"]
    assert _outcome(lambda: gfx.adj["zz"]) == _outcome(lambda: gnx.adj["zz"])


@pytest.mark.parametrize("cls_name", CLASSES)
def test_removed_node_stops_resolving_after_its_row_was_cached(cls_name):
    """The existence-proof assumption, stated as a test.

    Caching is only sound because ``remove_node`` bumps ``nodes_seq``. If it
    ever stopped doing so, a removed node would keep answering from the cache
    and this is the assertion that would catch it.
    """
    gnx, gfx = _pair(cls_name)
    for graph in (gnx, gfx):
        assert sorted(graph.adj["a"]) == ["b", "c"]
        graph.remove_node("a")
    assert _outcome(lambda: gfx.adj["a"]) == _outcome(lambda: gnx.adj["a"])
    assert _outcome(lambda: gfx.adj["a"])[0] == "raised"


@pytest.mark.parametrize("cls_name", CLASSES)
def test_cached_row_sees_later_edge_churn(cls_name):
    """Caching across edge mutation is legal only if the row live-reads."""
    gnx, gfx = _pair(cls_name)
    for graph in (gnx, gfx):
        graph.adj["a"]  # cache it
        graph.add_edge("a", "d")
    assert sorted(gfx.adj["a"]) == sorted(gnx.adj["a"]) == ["b", "c", "d"]
    for graph in (gnx, gfx):
        graph.remove_edge("a", "b")
    assert sorted(gfx.adj["a"]) == sorted(gnx.adj["a"]) == ["c", "d"]


@pytest.mark.parametrize("cls_name", CLASSES)
def test_assigned_node_override_does_not_hide_a_row_even_when_cached(cls_name):
    """br-r37-c1-ka7fd, in the order this reorder creates.

    Assigning ``_node`` does not bump ``nodes_seq``, so a row cached BEFORE the
    assignment is served by the fast path without consulting the override at
    all. That must match what the cold path does, which under ka7fd falls back
    to the adjacency and accepts a node with a real row.
    """
    gnx, gfx = _pair(cls_name)
    for graph in (gnx, gfx):
        graph.adj["a"]  # cache the row FIRST
        graph._node = {"b": {}, "c": {}}  # 'a' hidden from the node view
    assert sorted(gfx.adj["a"]) == sorted(gnx.adj["a"]) == ["b", "c"]

    # And with no prior caching, the cold path must reach the same answer.
    gnx2, gfx2 = _pair(cls_name)
    for graph in (gnx2, gfx2):
        graph._node = {"b": {}, "c": {}}
    assert sorted(gfx2.adj["a"]) == sorted(gnx2.adj["a"]) == ["b", "c"]


@pytest.mark.parametrize("cls_name", CLASSES)
def test_row_contents_and_membership_match_networkx(cls_name):
    gnx, gfx = _pair(cls_name)
    for _ in range(3):  # cold, then warm, then warm again
        for node in ("a", "b", "c"):
            assert sorted(gfx.adj[node]) == sorted(gnx.adj[node])
            assert len(gfx.adj[node]) == len(gnx.adj[node])
            for probe in ("a", "b", "c", "zz", 7):
                assert (probe in gfx.adj[node]) == (probe in gnx.adj[node])


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize(
    "bad", [["x"], {"x": 1}, {"x"}, bytearray(b"x")],
    ids=["list", "dict", "set", "bytearray"],
)
def test_unhashable_membership_in_a_row_raises_type_error(cls_name, bad):
    """br-r37-c1-espyz: `v in G.adj[u]` hashes v, so unhashable is TypeError.

    Simple `Graph` was the last class diverging here: its row is the NATIVE
    AtlasView (br-r37-c1-ey6ob routes it there), whose probe canonicalises by
    VALUE and never hashed, so it answered False where networkx raised. Checked
    on BOTH a cold row and a materialised one, because the native view has two
    membership branches and an answer that depends on which one is live would be
    the same cache-state bug br-r37-c1-alll4 pinned for node membership.
    """
    gnx, gfx = _pair(cls_name)
    cold = _outcome(lambda: bad in gfx.adj["a"])
    assert cold == _outcome(lambda: bad in gnx.adj["a"])
    assert cold[1] == "TypeError"

    row_fx, row_nx = gfx.adj["a"], gnx.adj["a"]
    list(row_fx)  # materialise the native row
    list(row_nx)
    warm = _outcome(lambda: bad in row_fx)
    assert warm == _outcome(lambda: bad in row_nx)
    assert warm[1] == "TypeError", "materialised row stopped hashing the key"


@pytest.mark.parametrize("cls_name", CLASSES)
def test_hashable_membership_is_unaffected_by_the_guard(cls_name):
    """The guard must not change any answer for a hashable key."""
    gnx, gfx = _pair(cls_name)
    for probe in ("a", "b", "c", "zz", 0, 7, -1, 2.5, True, (1, 2), frozenset({1}), ""):
        assert (probe in gfx.adj["a"]) == (probe in gnx.adj["a"]), probe
