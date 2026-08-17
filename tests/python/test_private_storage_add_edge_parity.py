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
