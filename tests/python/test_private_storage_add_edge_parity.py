"""br-r37-c1-wv3cu: add_edge and add_nodes_from write INTO the assigned mapping.

Same settled semantics as add_node — networkx's storage IS the assigned mapping,
and the caller keeps a reference, so a write that does not land there is simply
lost.

``add_nodes_from`` needs its own shadow even though ``add_node`` was already
fixed: networkx delegates the batch to ``add_node`` while fnx's batch is a native
kernel that never reaches it. That asymmetry is exactly what the mutation sweep
showed — add_node fixed, add_nodes_from still diverging — and it is the reason
"fixing the singular fixes the plural" cannot be assumed here.
"""

import copy

import networkx as nx
import pytest

import franken_networkx as fnx

ADJ = {"a": {"b": {}}, "b": {"a": {}}}
ALL = ["Graph", "MultiGraph", "DiGraph", "MultiDiGraph"]


def pair(cls, attr="_adj"):
    """Same graph in both libraries, each with its own copy of the mapping.

    The inner row object is SHARED between the two directions, because that is
    networkx's own invariant for an undirected edge — `_adj[u][v] is _adj[v][u]`.
    Building the two directions as separate dicts produces a mapping no real
    networkx graph would hold, and it made this fixture report a divergence that
    was the fixture's and not the code's: with the invariant respected, fnx and
    networkx agree exactly, down to object identity.

    Multigraphs carry a keydict per neighbour; simple graphs carry the attr dict.
    """
    out = []
    multi = cls.startswith("Multi")
    for mod in (nx, fnx):
        g = getattr(mod, cls)()
        g.add_edge("a", "b")
        shared = {0: {}} if multi else {}
        m = {"a": {"b": shared}, "b": {"a": shared}}
        setattr(g, attr, m)
        out.append((g, m))
    return out


def state(g):
    return (
        sorted(map(str, g.nodes)),
        sorted(str(tuple(map(str, e[:2]))) for e in g.edges),
        sorted(map(str, g.adj)),
    )


def build_with_assigned_storage(mod, cls, attr, mapping):
    """Give each implementation an independent, internally valid mapping."""
    graph = getattr(mod, cls)()
    graph.add_edge("a", "b")
    setattr(graph, attr, copy.deepcopy(mapping))
    return graph


def assigned_adjacency(cls):
    """A valid assigned row carrying ``ZZ`` only on the adjacency side."""
    if cls == "Graph":
        ab = {}
        return {"a": {"b": ab}, "b": {"a": ab}, "ZZ": {"b": {}}}
    if cls == "MultiGraph":
        ab = {0: {}}
        return {"a": {"b": ab}, "b": {"a": ab}, "ZZ": {"b": {0: {}}}}
    if cls == "DiGraph":
        return {"a": {"b": {}}, "b": {}, "ZZ": {"b": {}}}
    if cls == "MultiDiGraph":
        return {"a": {"b": {0: {}}}, "b": {}, "ZZ": {"b": {0: {}}}}
    raise AssertionError(f"unexpected graph class {cls}")


@pytest.mark.parametrize("cls", ALL)
def test_add_edge_reaches_the_callers_own_object(cls):
    (gnx, mnx), (gfx, mfx) = pair(cls)
    gnx.add_edge("p", "q")
    gfx.add_edge("p", "q")
    assert sorted(map(str, mfx)) == sorted(map(str, mnx))
    assert "p" in sorted(map(str, mnx)), "the case is only interesting if nx writes there"


@pytest.mark.parametrize("cls", ALL)
def test_add_edge_state_matches_networkx(cls):
    (gnx, _), (gfx, _) = pair(cls)
    gnx.add_edge("p", "q")
    gfx.add_edge("p", "q")
    assert state(gfx) == state(gnx)


@pytest.mark.parametrize("cls", ALL)
def test_add_edge_between_existing_nodes_matches(cls):
    (gnx, _), (gfx, _) = pair(cls)
    gnx.add_edge("a", "b", w=2)
    gfx.add_edge("a", "b", w=2)
    assert state(gfx) == state(gnx)
    assert gfx.get_edge_data("a", "b") == gnx.get_edge_data("a", "b")


@pytest.mark.parametrize("cls", ALL)
def test_add_nodes_from_reaches_the_assigned_mapping(cls):
    """Its own shadow: networkx delegates to add_node, fnx's native batch does not."""
    (gnx, mnx), (gfx, mfx) = pair(cls)
    gnx.add_nodes_from(["QQ", "RR"])
    gfx.add_nodes_from(["QQ", "RR"])
    assert sorted(map(str, mfx)) == sorted(map(str, mnx))
    assert state(gfx) == state(gnx)


@pytest.mark.parametrize("cls", ALL)
def test_add_nodes_from_with_attribute_tuples(cls):
    (gnx, _), (gfx, _) = pair(cls)
    gnx.add_nodes_from([("QQ", {"color": "red"}), "RR"], size=1)
    gfx.add_nodes_from([("QQ", {"color": "red"}), "RR"], size=1)
    assert dict(gfx.nodes["QQ"]) == dict(gnx.nodes["QQ"])
    assert dict(gfx.nodes["RR"]) == dict(gnx.nodes["RR"])


@pytest.mark.parametrize("cls", ALL)
def test_ordinary_graphs_are_unchanged(cls):
    """Negative control: shadows install only under private storage."""
    gnx = getattr(nx, cls)()
    gfx = getattr(fnx, cls)()
    for g in (gnx, gfx):
        g.add_edge("a", "b", w=1)
        g.add_edge("b", "c")
        g.add_nodes_from(["x", ("y", {"t": 2})])
    assert state(gfx) == state(gnx)
    assert dict(gfx.nodes["y"]) == dict(gnx.nodes["y"])
    assert not {"add_edge", "add_node", "add_nodes_from"} & set(vars(gfx))


@pytest.mark.parametrize(
    ("cls", "attr"),
    [
        ("Graph", "_adj"),
        ("MultiGraph", "_adj"),
        ("DiGraph", "_adj"),
        ("DiGraph", "_succ"),
        ("MultiDiGraph", "_adj"),
        ("MultiDiGraph", "_succ"),
    ],
)
def test_add_edge_uses_the_assigned_adjacency_as_networkx_does(cls, attr):
    """An assigned row can make a node exist only on the Python side.

    The classes do not all use the same membership authority: Graph checks
    ``_node`` while the multi/directed classes check their adjacency mapping.
    Calling the native method first conflated those two states, either retaining
    a row Graph must replace or inserting ``ZZ`` into fnx's native node store.
    """
    mapping = assigned_adjacency(cls)
    gnx = build_with_assigned_storage(nx, cls, attr, mapping)
    gfx = build_with_assigned_storage(fnx, cls, attr, mapping)
    gnx.add_edge("ZZ", "a")
    gfx.add_edge("ZZ", "a")
    assert state(gfx) == state(gnx)


@pytest.mark.parametrize("cls", ["Graph"])
def test_add_edge_keeps_networkxs_private_node_keyerror(cls):
    """A node-map-only assignment can know a node its adjacency lacks."""
    node_map = {"a": {}, "b": {}, "ZZ": {}}
    gnx = build_with_assigned_storage(nx, cls, "_node", node_map)
    gfx = build_with_assigned_storage(fnx, cls, "_node", node_map)
    with pytest.raises(Exception) as nx_error:
        gnx.add_edge("ZZ", "a")
    with pytest.raises(type(nx_error.value)) as fnx_error:
        gfx.add_edge("ZZ", "a")
    assert fnx_error.value.args == nx_error.value.args


@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiDiGraph"])
def test_remove_edge_uses_native_adjacency_when_only_node_is_assigned(cls):
    """``_node`` does not replace the edge mapping's authority."""
    node_map = {"a": {}, "b": {}, "ZZ": {}}
    gnx = build_with_assigned_storage(nx, cls, "_node", node_map)
    gfx = build_with_assigned_storage(fnx, cls, "_node", node_map)
    gnx.remove_edge("a", "b")
    gfx.remove_edge("a", "b")
    assert state(gfx) == state(gnx)


@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("attr", ["_adj", "_succ", "_node"])
def test_remove_node_preserves_networkxs_directed_error_message(cls, attr):
    """The graph class is observable in NetworkX's absent-node error."""
    mapping = assigned_adjacency(cls) if attr != "_node" else {"a": {}, "b": {}, "ZZ": {}}
    gnx = build_with_assigned_storage(nx, cls, attr, mapping)
    gfx = build_with_assigned_storage(fnx, cls, attr, mapping)
    with pytest.raises(Exception) as nx_error:
        gnx.remove_node("ZZ")
    with pytest.raises(type(nx_error.value)) as fnx_error:
        gfx.remove_node("ZZ")
    assert fnx_error.value.args == nx_error.value.args


@pytest.mark.parametrize("attr", ["_adj", "_succ"])
def test_directed_remove_edge_only_changes_the_assigned_forward_mapping(attr):
    """The reverse row is a separate directed edge, not an undirected twin."""
    mapping = {"a": {"b": {}}, "b": {"a": {}}, "ZZ": {"b": {}}}
    gnx = build_with_assigned_storage(nx, "DiGraph", attr, mapping)
    gfx = build_with_assigned_storage(fnx, "DiGraph", attr, mapping)
    gnx.remove_edge("a", "b")
    gfx.remove_edge("a", "b")
    assert state(gfx) == state(gnx)


@pytest.mark.parametrize("attr", ["_adj", "_succ"])
def test_directed_remove_edges_from_uses_the_assigned_mapping(attr):
    """The native batch kernel otherwise leaves a removed edge visible."""
    mapping = {"a": {"b": {}}, "b": {}, "ZZ": {"b": {}}}
    gnx = build_with_assigned_storage(nx, "DiGraph", attr, mapping)
    gfx = build_with_assigned_storage(fnx, "DiGraph", attr, mapping)
    gnx.remove_edges_from([("a", "b")])
    gfx.remove_edges_from([("a", "b")])
    assert state(gfx) == state(gnx)


def test_multigraph_private_only_edge_uses_networkxs_key_generator():
    """A non-integer key must not make the private-only branch sort keys."""
    ab = {0: {}}
    mapping = {
        "a": {"b": ab},
        "b": {"a": ab},
        "ZZ": {"a": {"external": {}}},
    }
    gnx = build_with_assigned_storage(nx, "MultiGraph", "_adj", mapping)
    gfx = build_with_assigned_storage(fnx, "MultiGraph", "_adj", mapping)
    assert gfx.add_edge("ZZ", "a", color="blue") == gnx.add_edge("ZZ", "a", color="blue")
    assert gfx._adj["ZZ"]["a"] == gnx._adj["ZZ"]["a"]
