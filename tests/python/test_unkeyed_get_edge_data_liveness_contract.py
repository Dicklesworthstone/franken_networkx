"""br-r37-c1-f3i50 — unkeyed `get_edge_data(u, v)` returns a DEAD SNAPSHOT.

networkx returns `self._adj[u][v]` itself — the graph's live keydict. fnx builds
a fresh `dict` per call whose VALUES are the live per-edge attr dicts. That makes
the inner half agree and everything else diverge.

THE BEAD UNDERSTATED THIS. It was filed as "new-key insertion does not reach the
graph". Enumerated against networkx on MultiGraph, EIGHT of ten observable
behaviours differ, and only two agree:

    operation                        nx      fnx     diverges
    identity across calls            True    False   yes
    d[k]['w'] = 9 propagates         True    True    no
    d[newkey] = {...} propagates     True    False   yes
    d.update({...}) propagates       True    False   yes
    del d[k] propagates              True    False   yes
    d.pop(k) propagates              True    False   yes
    d.clear() propagates             True    False   yes
    d.setdefault(k, {}) propagates   True    False   yes
    type(d) is dict                  True    True    no
    reflects a LATER add_edge        True    False   yes

THE LAST ROW IS THE ONE THAT CHANGES THE FIX. Every other divergence is a WRITE
that fails to reach the graph, and a write-proxying mapping would cover them. But
networkx's return value is also LIVE FOR READS: an edge added after the call
appears in a mapping the caller is still holding. A snapshot cannot do that at
any cost, so the fix has to hand back the live keydict — which is why this stays
blocked on br-r37-c1-himzq (multigraph rows have no live PyDict mirror) rather
than being fixable with a proxy object.

WHY THIS SURVIVED: the ONE thing most callers do — `G.get_edge_data(u, v)[k]['w']
= x` — works correctly, because the inner attr dicts are the live ones. A check
that exercised attribute mutation and stopped there would report this healthy,
and that is exactly what this pane nearly did before enumerating.

The diverging cases are `xfail(strict=True)`, so they fail loudly the moment the
behaviour is fixed and this file becomes the acceptance gate rather than a
record of a defect.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

MULTI = ["MultiGraph", "MultiDiGraph"]


def _pair(cls_name):
    gnx, gfx = getattr(nx, cls_name)(), getattr(fnx, cls_name)()
    for graph in (gnx, gfx):
        graph.add_edge("a", "b", w=1.0)
        graph.add_edge("a", "b", w=2.0)
        graph.add_edge("b", "c", w=3.0)
    return gnx, gfx


# --- the two behaviours that already agree -------------------------------


@pytest.mark.parametrize("cls_name", MULTI)
def test_inner_attr_mutation_propagates_in_both(cls_name):
    """The reason the defect went unnoticed: the common call works.

    This is a REGRESSION guard, not a defect record. Whatever fix lands for the
    rest must not break this, and a fix that returned a deep copy would.
    """
    gnx, gfx = _pair(cls_name)
    for graph in (gnx, gfx):
        graph.get_edge_data("a", "b")[0]["w"] = 99.0
    assert gfx["a"]["b"][0]["w"] == gnx["a"]["b"][0]["w"] == 99.0


@pytest.mark.parametrize("cls_name", MULTI)
def test_return_type_matches(cls_name):
    gnx, gfx = _pair(cls_name)
    assert type(gfx.get_edge_data("a", "b")) is type(gnx.get_edge_data("a", "b"))


@pytest.mark.parametrize("cls_name", MULTI)
def test_values_match_networkx(cls_name):
    """Value parity holds; it is liveness and identity that do not."""
    gnx, gfx = _pair(cls_name)
    for u, v in [("a", "b"), ("b", "c")]:
        want = {k: dict(d) for k, d in gnx.get_edge_data(u, v).items()}
        got = {k: dict(d) for k, d in gfx.get_edge_data(u, v).items()}
        assert got == want, (cls_name, u, v)
    assert gfx.get_edge_data("a", "zz") == gnx.get_edge_data("a", "zz")


@pytest.mark.parametrize("cls_name", MULTI)
def test_networkx_returns_its_own_live_keydict(cls_name):
    """Pins the INCUMBENT contract, so the target cannot drift unnoticed.

    THE TARGET IS `_adj[u][v]`, NOT `G[u][v]`, and an earlier draft of this file
    got that wrong. `G[u][v]` wraps the row in a read-only `AtlasView`, while
    `get_edge_data` hands back the raw storage dict underneath it — so the two
    are never identical even in networkx, and asserting against the wrapper made
    this test fail for a reason that had nothing to do with the defect.

    If a future networkx stopped returning the live row, the whole defect below
    would evaporate and these xfails would start passing for a reason that has
    nothing to do with fnx.
    """
    gnx = _pair(cls_name)[0]
    assert gnx.get_edge_data("a", "b") is gnx._adj["a"]["b"]


# --- the divergences ------------------------------------------------------


@pytest.mark.parametrize("cls_name", MULTI)
def test_returned_mapping_is_the_same_object_across_calls(cls_name):
    gfx = _pair(cls_name)[1]
    assert gfx.get_edge_data("a", "b") is gfx.get_edge_data("a", "b")


@pytest.mark.parametrize("cls_name", MULTI)
def test_returned_row_and_adjacency_view_share_live_attribute_dicts(cls_name):
    """A mutation through either access route is immediately visible through the other.

    ``G[u][v]`` is an AtlasView rather than the raw keydict, so it cannot be
    identical to ``get_edge_data(u, v)``.  Its per-key attribute dictionaries
    are nevertheless the same live objects, which is the observable
    write-through contract this row must preserve.
    """
    gfx = _pair(cls_name)[1]
    returned = gfx.get_edge_data("a", "b")
    adjacency = gfx["a"]["b"]

    assert returned[0] is adjacency[0]
    returned[0]["w"] = 41.0
    assert adjacency[0]["w"] == 41.0

    adjacency[1]["w"] = 42.0
    assert returned[1]["w"] == 42.0


@pytest.mark.parametrize("cls_name", MULTI)
@pytest.mark.xfail(strict=True, reason="br-r37-c1-f3i50: the returned mapping is a snapshot")
def test_returned_mapping_is_the_live_row(cls_name):
    """Compared against the RAW row, matching networkx's own invariant.

    `G[u][v]` is an `AtlasView` wrapper in both libraries, so it is the wrong
    target: networkx itself would fail that comparison.
    """
    gfx = _pair(cls_name)[1]
    assert gfx.get_edge_data("a", "b") is gfx._adj["a"]["b"]


@pytest.mark.parametrize("cls_name", MULTI)
@pytest.mark.xfail(strict=True, reason="br-r37-c1-f3i50: new-key insertion does not reach the graph")
def test_new_key_insertion_reaches_the_graph(cls_name):
    gfx = _pair(cls_name)[1]
    gfx.get_edge_data("a", "b")[7] = {"w": 7.0}
    assert 7 in gfx["a"]["b"]


@pytest.mark.parametrize("cls_name", MULTI)
@pytest.mark.xfail(strict=True, reason="br-r37-c1-f3i50: update does not reach the graph")
def test_update_reaches_the_graph(cls_name):
    gfx = _pair(cls_name)[1]
    gfx.get_edge_data("a", "b").update({8: {"w": 8.0}})
    assert 8 in gfx["a"]["b"]


@pytest.mark.parametrize("cls_name", MULTI)
@pytest.mark.xfail(strict=True, reason="br-r37-c1-f3i50: setdefault does not reach the graph")
def test_setdefault_reaches_the_graph(cls_name):
    gfx = _pair(cls_name)[1]
    gfx.get_edge_data("a", "b").setdefault(9, {"w": 9.0})
    assert 9 in gfx["a"]["b"]


@pytest.mark.parametrize("cls_name", MULTI)
@pytest.mark.xfail(strict=True, reason="br-r37-c1-f3i50: deletion does not reach the graph")
def test_deletion_reaches_the_graph(cls_name):
    gfx = _pair(cls_name)[1]
    del gfx.get_edge_data("a", "b")[0]
    assert 0 not in gfx["a"]["b"]


@pytest.mark.parametrize("cls_name", MULTI)
@pytest.mark.xfail(strict=True, reason="br-r37-c1-f3i50: pop does not reach the graph")
def test_pop_reaches_the_graph(cls_name):
    gfx = _pair(cls_name)[1]
    gfx.get_edge_data("a", "b").pop(1)
    assert 1 not in gfx["a"]["b"]


@pytest.mark.parametrize("cls_name", MULTI)
@pytest.mark.xfail(strict=True, reason="br-r37-c1-f3i50: clear does not reach the graph")
def test_clear_reaches_the_graph(cls_name):
    gfx = _pair(cls_name)[1]
    gfx.get_edge_data("a", "b").clear()
    assert len(gfx["a"]["b"]) == 0


@pytest.mark.parametrize("cls_name", MULTI)
def test_held_mapping_reflects_a_later_add_edge(cls_name):
    """A write-proxy would satisfy every other xfail here and still fail this.

    networkx hands back the row itself, so an edge added afterwards appears in a
    mapping the caller is still holding. That is why the fix needs the live
    keydict (br-r37-c1-himzq) and not a cleverer returned object.
    """
    gfx = _pair(cls_name)[1]
    held = gfx.get_edge_data("a", "b")
    gfx.add_edge("a", "b", key=5, w=5.0)
    assert 5 in held


def test_the_enumeration_is_not_vacuous():
    """Guards against every xfail above silently becoming unreachable."""
    gnx = nx.MultiGraph()
    gnx.add_edge("a", "b")
    assert gnx.get_edge_data("a", "b") is gnx._adj["a"]["b"], (
        "the incumbent no longer returns its live row; this whole file needs "
        "re-deriving against the new networkx contract"
    )
