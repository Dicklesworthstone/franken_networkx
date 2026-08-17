"""br-r37-c1-2ndmw — the multigraph row membership probe answers from INDICES.

`v in G.adj[u]` lands on the native `MultiAtlasView.__contains__`, and since the
shim's `AdjacencyView.__getitem__` uses `in` as its existence probe, so does
`G.adj[u][v]`. That probe used to build a canonical string for `v` and then hash
BOTH node keys inside the string `has_edge` — three operations linear in node key
length, for a question that is O(1) once both endpoints are indices. It now
resolves both to POSITIONS and probes by index.

WHAT THIS FILE GUARDS. The fast path caches this row's own position when the view
is built, which makes it stale-able in a way the string path never was:

  1. POSITIONS ARE RENUMBERED BY NODE REMOVAL. Remove a node that sorts before
     this row's node and every later position shifts down by one. A cached
     position that is not revalidated then names a DIFFERENT node, and the probe
     answers about the wrong pair — a wrong answer on an ordinary read, not a
     crash. The stamp is `nodes_seq`, which node add/remove bumps; these tests
     hold a row view across exactly that and demand the right answer.
  2. THE TWO INDEX SPACES. `cached_exact_string_node_index` and the captured row
     position are both POSITIONS, and `has_edge_by_indices` converts them to
     slots itself. Handing a position straight to the slot-keyed map reports a
     real edge as absent after a removal — see the Rust-side
     `multigraph_node_slot_and_position_are_distinct_index_spaces`.
  3. THE GATE. The path is entered only for exact `str` keys; every other key
     type, and every unhashable key, must behave exactly as before.

Every assertion compares against live networkx rather than a remembered value,
and each case is written to pass on a build WITHOUT the fast path too, so this
guards the change rather than describing it.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

MULTI = ["MultiGraph", "MultiDiGraph"]
LONG = "z" * 2000


def _pair(cls_name, edges, nodes=()):
    gnx, gfx = getattr(nx, cls_name)(), getattr(fnx, cls_name)()
    for graph in (gnx, gfx):
        for n in nodes:
            graph.add_node(n)
        for u, v in edges:
            graph.add_edge(u, v)
    return gnx, gfx


def _membership_agrees(gnx, gfx, row_node):
    """Every live node probed against both, through the row view."""
    rnx, rfx = gnx.adj[row_node], gfx.adj[row_node]
    for cand in list(gnx) + ["definitely-absent"]:
        if (cand in rnx) != (cand in rfx):
            return False, cand
    return True, None


@pytest.mark.parametrize("cls_name", MULTI)
@pytest.mark.parametrize("key_len", [1, len(LONG)])
def test_membership_matches_networkx(cls_name, key_len):
    """The plain case, at both key lengths the fast path is keyed on."""
    a, b, c = ("a" * key_len, "b" * key_len, "c" * key_len)
    gnx, gfx = _pair(cls_name, [(a, b), (a, b), (b, c)])
    for row_node in (a, b, c):
        ok, cand = _membership_agrees(gnx, gfx, row_node)
        assert ok, (cls_name, row_node, cand)


@pytest.mark.parametrize("cls_name", MULTI)
def test_held_row_view_survives_node_removal_that_renumbers_positions(cls_name):
    """THE regression this file exists for.

    `n0` sorts first, so removing it shifts every later node's position down by
    one. A row view captured before the removal holds a now-wrong position; if
    the stamp is not checked, membership answers about a different node.
    """
    gnx, gfx = _pair(
        cls_name,
        [("n2", "n3"), ("n2", "n3"), ("n1", "n4")],
        nodes=["n0", "n1", "n2", "n3", "n4"],
    )
    # Warm the row view BEFORE the mutation — a cold view cannot go stale.
    rfx_before = gfx.adj["n2"]
    assert ("n3" in rfx_before) is True
    assert ("n1" in rfx_before) is False

    for graph in (gnx, gfx):
        graph.remove_node("n0")

    # The held view must not answer from the pre-removal position.
    assert ("n3" in rfx_before) is True, "held row view lost a real edge"
    assert ("n1" in rfx_before) is False, "held row view invented an edge"
    ok, cand = _membership_agrees(gnx, gfx, "n2")
    assert ok, cand


@pytest.mark.parametrize("cls_name", MULTI)
def test_held_row_view_survives_node_addition(cls_name):
    """Addition bumps the same counter; the stamp must not reject wrongly either."""
    gnx, gfx = _pair(cls_name, [("n1", "n2")], nodes=["n1", "n2"])
    rfx = gfx.adj["n1"]
    assert ("n2" in rfx) is True
    for graph in (gnx, gfx):
        graph.add_node("n0")
        graph.add_edge("n1", "n3")
    assert ("n2" in rfx) is True
    assert ("n3" in rfx) is True
    assert ("n0" in rfx) is False
    ok, cand = _membership_agrees(gnx, gfx, "n1")
    assert ok, cand


@pytest.mark.parametrize("cls_name", MULTI)
def test_membership_after_removing_the_edge_but_not_the_nodes(cls_name):
    """Edge removal does not renumber positions, so this exercises the fast path
    staying correct when the stamp is still VALID."""
    gnx, gfx = _pair(cls_name, [("a", "b"), ("a", "b")])
    rfx = gfx.adj["a"]
    assert ("b" in rfx) is True
    for graph in (gnx, gfx):
        graph.remove_edge("a", "b")
    assert ("b" in rfx) is True, "one parallel edge remains"
    for graph in (gnx, gfx):
        graph.remove_edge("a", "b")
    assert ("b" in rfx) is False, "last parallel edge gone"
    ok, cand = _membership_agrees(gnx, gfx, "a")
    assert ok, cand


@pytest.mark.parametrize("cls_name", MULTI)
def test_non_string_keys_take_the_slow_path_and_stay_correct(cls_name):
    """The gate is exact-`str`; ints, tuples and floats must be unaffected."""
    gnx, gfx = _pair(cls_name, [(1, 2), (1, 2), (2, 3)])
    rnx, rfx = gnx.adj[1], gfx.adj[1]
    for cand in (1, 2, 3, 99, (1, 2), 2.0, True):
        assert (cand in rfx) == (cand in rnx), cand


@pytest.mark.parametrize("cls_name", MULTI)
def test_unhashable_key_is_a_typeerror(cls_name):
    """networkx hashes the key, so an unhashable one raises rather than
    answering False. The fast path must not swallow that."""
    gnx, gfx = _pair(cls_name, [("a", "b")])
    for key in (["x"], {"a": 1}, {1, 2}):
        with pytest.raises(TypeError):
            key in gnx.adj["a"]
        with pytest.raises(TypeError):
            key in gfx.adj["a"]


@pytest.mark.parametrize("cls_name", MULTI)
def test_native_row_view_directly(cls_name):
    """Reach the native view without the Python wrapper in front of it.

    The shim's `AdjacencyView.__contains__` has its own short-circuits, so a
    defect in the native probe can hide behind them; this pins the object the
    change actually edits.
    """
    gnx, gfx = _pair(
        cls_name, [("n2", "n3"), ("n1", "n4")], nodes=["n0", "n1", "n2", "n3", "n4"]
    )
    accessor = getattr(gfx, "_native_adjacency_row", None)
    if accessor is None:
        pytest.skip("this build exposes no _native_adjacency_row")
    native = accessor("n2")
    assert ("n3" in native) is True
    assert ("n1" in native) is False
    gnx.remove_node("n0")
    gfx.remove_node("n0")
    assert ("n3" in native) is True, "native row view stale after renumbering"
    assert ("n1" in native) is False
    for cand in list(gnx):
        assert (cand in native) == (cand in gnx.adj["n2"]), cand


@pytest.mark.parametrize("cls_name", MULTI)
def test_self_loop_membership(cls_name):
    """A self loop makes the row contain its own node — an easy off-by-one for
    any index pairing that assumes u != v."""
    gnx, gfx = _pair(cls_name, [("a", "a"), ("a", "b")])
    assert ("a" in gfx.adj["a"]) == ("a" in gnx.adj["a"]) is True
    assert ("b" in gfx.adj["a"]) == ("b" in gnx.adj["a"]) is True


@pytest.mark.parametrize("cls_name", MULTI)
def test_directionality_is_preserved(cls_name):
    """MultiDiGraph rows are OUT edges; the index probe must not become
    symmetric on the directed class."""
    gnx, gfx = _pair(cls_name, [("src", "dst")])
    assert ("dst" in gfx.adj["src"]) == ("dst" in gnx.adj["src"]) is True
    assert ("src" in gfx.adj["dst"]) == ("src" in gnx.adj["dst"])
    if cls_name == "MultiDiGraph":
        assert ("src" in gnx.adj["dst"]) is False, "networkx oracle changed"
