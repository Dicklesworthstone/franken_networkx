"""br-r37-c1-nbrow — the node-index twin of the adjacency row cache must never go stale.

`G.neighbors(n)` is `iter(self._adj[n])` in networkx: one dict lookup on a str
whose hash CPython caches. fnx reaches a cached row dict, but probed it with a
canonical built from the key's bytes and then hashed those bytes, so a cache HIT
was O(node key length):

    K=2     246.5 ns   ratio 0.656
    K=2000 1055.7 ns   ratio 0.149      a 4.3x slope

while `has_edge`, which already had an index route, is flat over the same span
(200.4 ns against 198.8 ns). The twin resolves the node through the cached `str`
hash instead.

THE TWIN IS STAMPED WITH `nodes_seq` ALONE, which is the interesting risk. A
`nodes_seq`-only stamp is exactly what went wrong once before on the keydict
twin, where an EDGE mutation invalidated a cached value the stamp could not see.
Two properties make it safe here, and BOTH are pinned below rather than trusted:

  1. Every site that removes a row from the string-keyed cache bumps `nodes_seq`
     immediately, so a removed row's stamp goes stale by itself.
  2. The cached value is the SAME dict object the string-keyed cache holds, and
     edge changes MAINTAIN that dict IN PLACE rather than replacing it — so an
     edge mutation is visible through the twin with no invalidation at all.

Property 2 is the one worth attacking: if it ever stops holding, the twin serves
a row missing its newest neighbours, and `G.neighbors` silently omits edges. The
mutation cases below all WARM the row first, because a cold read cannot expose a
stale cache.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]

REMOVE_READD = (
    "br-r37-c1-clrow, SECOND half: removing a node and re-adding it leaves a "
    "stale neighbour row on BOTH multigraph classes. Distinct from the clear() "
    "half fixed here — clear() empties the map, whereas remove_node leaves the "
    "removed node's own row behind and the re-add resurrects it. Found by this "
    "file; not fixed, because the fix needs a build and the host is under a "
    "build halt."
)

MDG_CLEAR = (
    "br-r37-c1-clrow: MultiDiGraph::clear() has a different code shape from "
    "MultiGraph::clear(), so the one-line drop of neighbor_key_rows landed only "
    "on the undirected class. Same defect, same fix, needs a build to verify."
)
LONG = "z" * 2000


def _pair(cls_name):
    return getattr(nx, cls_name)(), getattr(fnx, cls_name)()


def _nbrs(g, n):
    return sorted(map(str, g.neighbors(n)))


def _same(gnx, gfx, n):
    return _nbrs(gfx, n) == _nbrs(gnx, n)


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("key_len", [2, len(LONG)])
def test_neighbors_matches_networkx(cls_name, key_len):
    """Both key lengths: the index route is exact-`str` gated and only engages
    for string nodes, so the short case proves the fall-through still works."""
    u = "u" * key_len
    gnx, gfx = _pair(cls_name)
    for g in (gnx, gfx):
        for i in range(4):
            g.add_edge(u, f"n{i}".ljust(key_len, "x"))
    assert _same(gnx, gfx, u)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_warm_then_add_edge_is_visible(cls_name):
    """PROPERTY 2. An edge added after the row is warm must appear — this is the
    case a `nodes_seq`-only stamp cannot see, and it is safe only because the row
    dict is maintained in place."""
    gnx, gfx = _pair(cls_name)
    for g in (gnx, gfx):
        g.add_edge("hub", "a")
    assert _same(gnx, gfx, "hub")          # warm
    for g in (gnx, gfx):
        g.add_edge("hub", "b")
    assert _same(gnx, gfx, "hub"), "edge added after warming is invisible"
    for g in (gnx, gfx):
        g.add_edge("hub", "c")
        g.add_edge("d", "hub")
    assert _same(gnx, gfx, "hub")


@pytest.mark.parametrize("cls_name", CLASSES)
def test_warm_then_remove_edge_is_visible(cls_name):
    gnx, gfx = _pair(cls_name)
    for g in (gnx, gfx):
        g.add_edge("hub", "a")
        g.add_edge("hub", "b")
    assert _same(gnx, gfx, "hub")          # warm
    for g in (gnx, gfx):
        g.remove_edge("hub", "a")
    assert _same(gnx, gfx, "hub"), "edge removed after warming is still reported"


@pytest.mark.parametrize("cls_name", CLASSES)
def test_warm_then_remove_a_node_renumbers_indices(cls_name):
    """PROPERTY 1. Removing an earlier node shifts every later index. A twin
    entry keyed by a bare index would then answer for a DIFFERENT node."""
    gnx, gfx = _pair(cls_name)
    for g in (gnx, gfx):
        for n in ("n0", "n1", "n2", "n3"):
            g.add_node(n)
        g.add_edge("n2", "n3")
        g.add_edge("n1", "n2")
    assert _same(gnx, gfx, "n2")           # warm
    for g in (gnx, gfx):
        g.remove_node("n0")
    assert _same(gnx, gfx, "n2"), "index resolved to the wrong node after renumbering"
    assert _same(gnx, gfx, "n1")
    assert _same(gnx, gfx, "n3")


@pytest.mark.parametrize(
    "cls_name",
    [
        "Graph",
        "DiGraph",
        pytest.param("MultiGraph", marks=pytest.mark.xfail(strict=True, reason=REMOVE_READD)),
        pytest.param("MultiDiGraph", marks=pytest.mark.xfail(strict=True, reason=REMOVE_READD)),
    ],
)
def test_warm_then_remove_and_readd_the_same_node(cls_name):
    """A re-added node may land on a different index with a different row."""
    gnx, gfx = _pair(cls_name)
    for g in (gnx, gfx):
        g.add_edge("hub", "a")
        g.add_edge("other", "b")
    assert _same(gnx, gfx, "hub")          # warm
    for g in (gnx, gfx):
        g.remove_node("hub")
        g.add_edge("hub", "c")
    assert _same(gnx, gfx, "hub"), "stale row survived a remove/re-add"
    assert _same(gnx, gfx, "other")


@pytest.mark.parametrize(
    "cls_name",
    [
        "Graph",
        "DiGraph",
        "MultiGraph",
        pytest.param("MultiDiGraph", marks=pytest.mark.xfail(strict=True, reason=MDG_CLEAR)),
    ],
)
def test_warm_then_clear_the_graph(cls_name):
    """`clear()` empties the string-keyed cache; a twin entry outliving it would
    serve a dict that in-place maintenance can no longer reach."""
    gnx, gfx = _pair(cls_name)
    for g in (gnx, gfx):
        g.add_edge("hub", "a")
    assert _same(gnx, gfx, "hub")          # warm
    for g in (gnx, gfx):
        g.clear()
        g.add_edge("hub", "z")
    assert _same(gnx, gfx, "hub"), "stale row survived clear()"


@pytest.mark.parametrize("cls_name", CLASSES)
def test_non_string_nodes_take_the_fallback(cls_name):
    """The probe is exact-`str` gated; ints, tuples and floats are unaffected."""
    gnx, gfx = _pair(cls_name)
    for g in (gnx, gfx):
        g.add_edge(1, 2)
        g.add_edge(1, (3, 4))
        g.add_edge(1, 5.5)
    assert _same(gnx, gfx, 1)
    for g in (gnx, gfx):
        g.add_edge(1, 9)
    assert _same(gnx, gfx, 1)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_absent_node_raises_networkxs_error(cls_name):
    gnx, gfx = _pair(cls_name)
    for g in (gnx, gfx):
        g.add_edge("a", "b")
    want = got = None
    try:
        list(gnx.neighbors("missing"))
    except Exception as exc:  # noqa: BLE001
        want = (type(exc).__name__, exc.args)
    try:
        list(gfx.neighbors("missing"))
    except Exception as exc:  # noqa: BLE001
        got = (type(exc).__name__, exc.args)
    assert got == want


@pytest.mark.parametrize("cls_name", CLASSES)
def test_iterator_runtime_type_still_matches(cls_name):
    """networkx yields a `dict_keyiterator`; the index route must not change the
    object handed back, only how it is found."""
    gnx, gfx = _pair(cls_name)
    for g in (gnx, gfx):
        g.add_edge("a", "b")
    assert type(gfx.neighbors("a")).__name__ == type(gnx.neighbors("a")).__name__


@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
def test_direction_is_preserved(cls_name):
    """`neighbors` is SUCCESSORS on a directed graph; a row keyed by index must
    not start reporting predecessors."""
    gnx, gfx = _pair(cls_name)
    for g in (gnx, gfx):
        g.add_edge("src", "dst")
        g.add_edge("pred", "src")
    assert _same(gnx, gfx, "src")
    assert _nbrs(gfx, "src") == ["dst"], "neighbors leaked a predecessor"


NEIGHBOUR_ROW = (
    "br-r37-c1-txkrn: on MultiGraph a NEIGHBOUR's warm row keeps a node that was "
    "removed — neighbors('a') reports 'hub' after remove_node('hub'). Third "
    "manifestation of the same laundering: remove_node bumps nodes_seq but never "
    "drops the row, and the next add_edge calls restamp_neighbor_rows, writing "
    "the current sequences over the stale one. Undirected only; MultiDiGraph "
    "keeps per-direction rows and is correct here."
)

MDG_SUCC_CLEAR = (
    "br-r37-c1-txkrn: MultiDiGraph::clear() clears neither succ_key_rows nor "
    "pred_key_rows, so successors() reports a pre-clear neighbour. Same defect "
    "as the MultiGraph clear() half fixed in 73da7cdd1, which did not match "
    "because the directed clear() has a different shape and TWO maps."
)


@pytest.mark.parametrize(
    "cls_name",
    [
        "Graph",
        "DiGraph",
        pytest.param("MultiGraph", marks=pytest.mark.xfail(strict=True, reason=NEIGHBOUR_ROW)),
        "MultiDiGraph",
    ],
)
def test_a_neighbours_row_drops_a_removed_node(cls_name):
    """Not the removed node's OWN row — the row of a node that merely pointed at
    it. Warmed first, because a cold read cannot expose a stale cache."""
    gnx, gfx = _pair(cls_name)
    for g in (gnx, gfx):
        g.add_edge("hub", "a")
        g.add_edge("a", "b")
    assert _same(gnx, gfx, "a")            # warm A's row
    for g in (gnx, gfx):
        g.remove_node("hub")
        g.add_edge("a", "c")               # triggers the restamp
    assert _same(gnx, gfx, "a"), "a neighbour's row still reports the removed node"


@pytest.mark.xfail(strict=True, reason=MDG_SUCC_CLEAR)
def test_successors_after_clear_on_the_directed_multigraph():
    """The directed row caches are per-direction, so `successors` has its own
    exposure to the clear() defect."""
    gnx, gfx = _pair("MultiDiGraph")
    for g in (gnx, gfx):
        g.add_edge("hub", "a")
    assert sorted(map(str, gfx.successors("hub"))) == sorted(map(str, gnx.successors("hub")))
    for g in (gnx, gfx):
        g.clear()
        g.add_edge("hub", "z")
    assert sorted(map(str, gfx.successors("hub"))) == sorted(map(str, gnx.successors("hub")))
