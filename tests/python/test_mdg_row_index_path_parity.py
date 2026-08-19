"""MultiDiGraph row membership must not change answer when served from indices.

br-r37-c1-2ndmw. `MultiDiAtlasView::__contains__` gained an index-keyed fast path
(the directed twin of `MultiAtlasView`'s). It is guarded three ways and each guard
has a negative case here that a naive port fails:

  * ORIENTATION. `has_edge_by_indices` is source-major, but the row is the SOURCE
    for a successor row and the TARGET for a predecessor row, so the positions
    swap with the row kind. A port that hands them over in row order answers about
    the reversed edge -- which on a digraph is a different edge. `test_direction_*`
    fails loudly for that port and passes for the string path.
  * RENUMBERING. Node removal renumbers positions, so a cached position can come
    to name a DIFFERENT node. An unstamped cache reports another node's edge as
    present. `test_row_held_across_node_removal` is that case.
  * UNHASHABLE keys must still raise TypeError, not answer False.

Every assertion is against networkx running the same scenario, so it pins the
incumbent's contract rather than fnx's current answers.
"""

import networkx as nx
import pytest

import franken_networkx as fnx

KEYLENS = [3, 2000]


def _pair(keylen):
    return "u" * keylen, "v" * keylen


def _build(module, keylen):
    graph = module.MultiDiGraph()
    u, v = _pair(keylen)
    graph.add_edge(u, v, weight=1)
    for i in range(50):
        graph.add_edge(f"a{i}", f"b{i}")
    return graph, u, v


@pytest.mark.parametrize("keylen", KEYLENS)
def test_direction_successor_row(keylen):
    """`v in G[u]` is True and `u in G[v]` is False -- the edge is u->v only."""
    for module in (nx, fnx):
        graph, u, v = _build(module, keylen)
        assert v in graph[u], f"{module.__name__}: v must be a successor of u"
        assert u not in graph[v], (
            f"{module.__name__}: u must NOT be a successor of v -- an index path "
            f"that ignores orientation answers True here"
        )


@pytest.mark.parametrize("keylen", KEYLENS)
def test_direction_predecessor_row(keylen):
    """`u in G.pred[v]` is True and `v in G.pred[u]` is False.

    The predecessor row is where the position swap matters: this row's own node is
    the TARGET, so handing (row, other) to a source-major probe asks about v->u.
    """
    for module in (nx, fnx):
        graph, u, v = _build(module, keylen)
        assert u in graph.pred[v], f"{module.__name__}: u must be a predecessor of v"
        assert v not in graph.pred[u], (
            f"{module.__name__}: v must NOT be a predecessor of u -- this is the "
            f"assertion an unswapped index path fails"
        )


@pytest.mark.parametrize("keylen", KEYLENS)
@pytest.mark.parametrize("row_kind", ["succ", "pred"])
def test_row_held_across_node_removal(keylen, row_kind):
    """A row held across a node removal must not answer from a stale position.

    Removing a node renumbers insertion-order positions, so a cached position can
    now name a different node. The probe must re-resolve, not answer from the
    stale entry. Compared against networkx, which has no such cache and is
    therefore the oracle for what the answers should be.
    """
    outcomes = {}
    for name, module in (("nx", nx), ("fnx", fnx)):
        graph, u, v = _build(module, keylen)
        # Hold the row BEFORE the removal so any cached position predates it.
        row = graph.pred[v] if row_kind == "pred" else graph[u]
        probe = u if row_kind == "pred" else v
        before = probe in row
        # Remove earlier-inserted nodes so every later position shifts.
        for i in range(10):
            graph.remove_node(f"a{i}")
        after = probe in row
        # And a node that was never adjacent must still be absent.
        stranger = "b40" in row
        outcomes[name] = (before, after, stranger)
    assert outcomes["fnx"] == outcomes["nx"], (
        f"MultiDiGraph {row_kind} row held across node removal: networkx gave "
        f"{outcomes['nx']}, fnx gave {outcomes['fnx']} for "
        f"(before_removal, after_removal, never_adjacent)."
    )


@pytest.mark.parametrize("keylen", KEYLENS)
def test_unhashable_probe_raises_typeerror(keylen):
    """An unhashable key is networkx's TypeError, not False."""
    for module in (nx, fnx):
        graph, u, _v = _build(module, keylen)
        with pytest.raises(TypeError):
            _ = [1] in graph[u]


@pytest.mark.parametrize("keylen", KEYLENS)
def test_non_string_keys_still_answer(keylen):
    """The index path is gated on exact `str`; other key types take the old path.

    Carried because the gate is easy to write as "any string-ish" and int/tuple
    keys would then be resolved through a cache that never holds them.
    """
    outcomes = {}
    for name, module in (("nx", nx), ("fnx", fnx)):
        graph = module.MultiDiGraph()
        graph.add_edge(1, 2, weight=1)
        graph.add_edge((3, 4), (5, 6), weight=1)
        outcomes[name] = (
            2 in graph[1],
            1 in graph[2],
            (5, 6) in graph[(3, 4)],
            (3, 4) in graph[(5, 6)],
        )
    assert outcomes["fnx"] == outcomes["nx"], (
        f"non-str node keys: networkx gave {outcomes['nx']}, fnx gave {outcomes['fnx']}"
    )


@pytest.mark.parametrize("keylen", KEYLENS)
def test_row_reflects_edges_added_after_it_was_built(keylen):
    """The row is live for EDGE changes; only node churn moves positions."""
    outcomes = {}
    for name, module in (("nx", nx), ("fnx", fnx)):
        graph, u, _v = _build(module, keylen)
        row = graph[u]
        w = "w" * keylen
        graph.add_node(w)
        before = w in row
        graph.add_edge(u, w, weight=2)
        outcomes[name] = (before, w in row)
    assert outcomes["fnx"] == outcomes["nx"], (
        f"row liveness across edge insertion: networkx gave {outcomes['nx']}, "
        f"fnx gave {outcomes['fnx']}"
    )
