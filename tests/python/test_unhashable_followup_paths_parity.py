"""Parity for the 3 remaining unhashable-node paths after br-r37-c1-m0io3.

Bead br-r37-c1-g438p (follow-up to br-r37-c1-m0io3). Three paths
still accepted (or mis-classified) unhashable inputs after the
initial fix:

(1) ``add_weighted_edges_from``: silently accepted unhashable
    endpoints; nx raises TypeError.

(2) ``remove_node``: raised ``NetworkXError("not in graph")`` after
    a silent-False membership check; nx raises TypeError before the
    membership check.

(3) ``Graph(...)`` constructor with edge-list containing unhashable
    endpoints: silently absorbed via the Rust ``__new__`` (storing
    by Python id); nx raises ``NetworkXError("Input is not a valid
    edge list")``.

The fix validates ``hash(node)`` on each endpoint at the wrapper
edge: ``add_weighted_edges_from`` mirrors the ``add_edges_from``
pattern, ``remove_node`` adds a hash check before membership,
and ``__init__`` validates absorbed nodes for the passthrough path
(skipping numpy/pandas/Graph special cases that clear+rebuild).
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")

UNHASHABLE = [
    pytest.param([1, 2], id="list"),
    pytest.param({1, 2}, id="set"),
    pytest.param({"a": 1}, id="dict"),
]


# ---------------------------------------------------------------------------
# add_weighted_edges_from
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize("val", UNHASHABLE)
def test_add_weighted_edges_from_unhashable_endpoint_raises(val):
    G = fnx.Graph()
    GX = nx.Graph()
    with pytest.raises(TypeError, match=r"unhashable type"):
        G.add_weighted_edges_from([(val, 3, 1.0)])
    with pytest.raises(TypeError, match=r"unhashable type"):
        GX.add_weighted_edges_from([(val, 3, 1.0)])


@needs_nx
def test_add_weighted_edges_from_hashable_unchanged():
    """Regression — hashable endpoints still produce the expected
    weighted graph."""
    edges = [(1, 2, 1.5), (3, 4, 2.0)]
    G = fnx.Graph()
    GX = nx.Graph()
    G.add_weighted_edges_from(edges)
    GX.add_weighted_edges_from(edges)
    assert sorted(G.edges(data=True)) == sorted(GX.edges(data=True))


# ---------------------------------------------------------------------------
# remove_node
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize("val", UNHASHABLE)
def test_remove_node_unhashable_raises_type_error(val):
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    with pytest.raises(TypeError, match=r"unhashable type"):
        G.remove_node(val)
    with pytest.raises(TypeError, match=r"unhashable type"):
        GX.remove_node(val)


@needs_nx
def test_remove_node_missing_hashable_still_raises_networkxerror():
    """A missing-but-hashable node still raises NetworkXError —
    only unhashable inputs trigger TypeError."""
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    with pytest.raises(fnx.NetworkXError):
        G.remove_node(99)
    with pytest.raises(nx.NetworkXError):
        GX.remove_node(99)


# ---------------------------------------------------------------------------
# Graph(...) constructor with edge-list containing unhashable
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize("val", UNHASHABLE)
@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_constructor_edge_list_unhashable_endpoint_raises(val, cls_name):
    """nx raises ``NetworkXError("Input is not a valid edge list")``
    when an edge-list contains an unhashable endpoint. fnx now
    matches the exception class and message."""
    cls = getattr(fnx, cls_name)
    cls_n = getattr(nx, cls_name)
    with pytest.raises(fnx.NetworkXError, match=r"Input is not a valid edge list"):
        cls([(val, 3)])
    with pytest.raises(nx.NetworkXError, match=r"Input is not a valid edge list"):
        cls_n([(val, 3)])


# ---------------------------------------------------------------------------
# Special-case constructor inputs unaffected by the new hash check
# ---------------------------------------------------------------------------

@needs_nx
def test_constructor_numpy_adjacency_unchanged():
    """Numpy adjacency input goes through a clear+rebuild branch,
    so the new hash check must not fire on numpy ndarray rows
    (which are themselves unhashable but only transiently absorbed
    by the Rust __new__)."""
    np = pytest.importorskip("numpy")
    A = np.array([[0, 1, 0], [1, 0, 1], [0, 1, 0]])
    G = fnx.Graph(A)
    GX = nx.Graph(A)
    assert sorted(G.edges()) == sorted(GX.edges())


@needs_nx
def test_constructor_pandas_adjacency_unchanged():
    pd = pytest.importorskip("pandas")
    np = pytest.importorskip("numpy")
    A = pd.DataFrame([[0, 1, 0], [1, 0, 1], [0, 1, 0]])
    G = fnx.Graph(A)
    GX = nx.Graph(A)
    assert sorted(G.edges()) == sorted(GX.edges())


@needs_nx
def test_constructor_from_graph_unchanged():
    src = fnx.Graph([(1, 2), (2, 3)])
    G = fnx.Graph(src)
    assert sorted(G.edges()) == [(1, 2), (2, 3)]


@needs_nx
def test_constructor_dict_of_list_unchanged():
    G = fnx.Graph({1: [2], 2: [3]})
    GX = nx.Graph({1: [2], 2: [3]})
    assert sorted(G.edges()) == sorted(GX.edges())


@needs_nx
def test_constructor_edge_list_hashable_unchanged():
    edges = [(1, 2), ((3, 4), (5, 6))]
    G = fnx.Graph(edges)
    GX = nx.Graph(edges)
    assert sorted(map(str, G.nodes())) == sorted(map(str, GX.nodes()))
