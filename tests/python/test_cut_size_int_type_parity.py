"""Parity for ``cut_size`` int/float return type.

Bead br-r37-c1-f47su. fnx.cut_size always returned a float (1.0, 2.0)
regardless of input weight type. nx.cut_size preserves int when the
result is integer (always for unweighted, and when all relevant
weights are int). Drop-in code that asserts
``isinstance(cut_size(G, S), int)`` broke.
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


@needs_nx
def test_unweighted_returns_int():
    G = fnx.path_graph(5)
    GX = nx.path_graph(5)
    f = fnx.cut_size(G, [0, 1])
    n = nx.cut_size(GX, [0, 1])
    assert f == n == 1
    assert isinstance(f, int)
    assert type(f) is type(n)


@needs_nx
def test_weighted_int_returns_int():
    G = fnx.Graph()
    G.add_edge(0, 1, weight=2)
    G.add_edge(1, 2, weight=3)
    GX = nx.Graph()
    GX.add_edge(0, 1, weight=2)
    GX.add_edge(1, 2, weight=3)
    f = fnx.cut_size(G, [0], weight="weight")
    n = nx.cut_size(GX, [0], weight="weight")
    assert f == n == 2
    assert isinstance(f, int)


@needs_nx
def test_weighted_float_returns_float():
    """Float weights must stay float."""
    G = fnx.Graph()
    G.add_edge(0, 1, weight=2.5)
    GX = nx.Graph()
    GX.add_edge(0, 1, weight=2.5)
    f = fnx.cut_size(G, [0], weight="weight")
    n = nx.cut_size(GX, [0], weight="weight")
    assert f == n == 2.5
    assert isinstance(f, float)


@needs_nx
def test_unweighted_with_S_T():
    G = fnx.path_graph(5)
    GX = nx.path_graph(5)
    f = fnx.cut_size(G, [0, 1], [2, 3])
    n = nx.cut_size(GX, [0, 1], [2, 3])
    assert type(f) is type(n)


@needs_nx
def test_zero_cut_returns_int():
    """A cut of zero edges should still be int 0, not float 0.0."""
    G = fnx.Graph()
    G.add_nodes_from([0, 1, 2])
    GX = nx.Graph()
    GX.add_nodes_from([0, 1, 2])
    f = fnx.cut_size(G, [0])
    n = nx.cut_size(GX, [0])
    assert f == n == 0
    assert isinstance(f, int)


@needs_nx
def test_selfloop_unweighted_returns_int():
    """Self-loops contribute 1 each — result is int."""
    G = fnx.Graph([(0, 0), (0, 1)])
    GX = nx.Graph([(0, 0), (0, 1)])
    f = fnx.cut_size(G, [0])
    n = nx.cut_size(GX, [0])
    assert type(f) is type(n)


@needs_nx
def test_mixed_int_float_weights_returns_float():
    """If any edge in the cut has a float weight, result is float."""
    G = fnx.Graph()
    G.add_edge(0, 1, weight=2)
    G.add_edge(1, 2, weight=2.5)
    GX = nx.Graph()
    GX.add_edge(0, 1, weight=2)
    GX.add_edge(1, 2, weight=2.5)
    f = fnx.cut_size(G, [0, 1], weight="weight")
    n = nx.cut_size(GX, [0, 1], weight="weight")
    assert f == n
    assert isinstance(f, float) == isinstance(n, float)


@needs_nx
def test_directed_cut_size_with_explicit_T():
    """On DiGraph with explicit S and T, fnx matches nx exactly."""
    edges = [("s", "m"), ("m", "t"), ("s", "t"), ("m", "x"), ("x", "t"), ("t", "s")]
    G = fnx.DiGraph()
    GX = nx.DiGraph()
    for u, v in edges:
        G.add_edge(u, v, weight=2)
        GX.add_edge(u, v, weight=2)

    S = {"s", "m"}
    T = set(G.nodes()) - S
    f = fnx.cut_size(G, S, T, weight="weight")
    n = nx.cut_size(GX, S, T, weight="weight")
    assert f == n == 8
    assert isinstance(f, int)


@needs_nx
def test_directed_cut_size_default_T_upstream_bug():
    """br-r37-c1-lh8oi: On DiGraph with T=None, upstream networkx 3.6.1 crashes with
    TypeError ('NoneType' object is not iterable) in edge_boundary(G, T, S) because
    it forgets to default T to V \\ S before the reverse boundary call.
    FrankenNetworkX computes the mathematically defined cut size against V \\ S,
    matching what networkx returns when T is explicitly given as V \\ S.
    """
    edges = [("s", "m"), ("m", "t"), ("s", "t"), ("m", "x"), ("x", "t"), ("t", "s")]
    G = fnx.DiGraph()
    GX = nx.DiGraph()
    for u, v in edges:
        G.add_edge(u, v, weight=2)
        GX.add_edge(u, v, weight=2)

    S = {"s", "m"}
    T_explicit = set(G.nodes()) - S

    # fnx with T=None matches fnx with explicit T
    assert fnx.cut_size(G, S, weight="weight") == fnx.cut_size(G, S, T_explicit, weight="weight")

    # fnx with T=None matches what nx returns with explicit T
    assert fnx.cut_size(G, S, weight="weight") == nx.cut_size(GX, S, T_explicit, weight="weight")

    # Upstream nx crashes on T=None
    with pytest.raises(TypeError, match=".*NoneType.*object is not iterable.*"):
        nx.cut_size(GX, S, weight="weight")


# br-r37-c1-rjgh0: nx sums the crossing edges from the int 0, so an EMPTY cut is
# 0 whatever the weights; the native kernel's f64 sum of nothing is -0.0, which
# the wrapper returned on float-weighted graphs (and edge_expansion /
# mixing_expansion divided it into -0.0). repr() tells 0, 0.0 and -0.0 apart.
_CUT_EDGES = {
    "float": [(0, 1, 2.5), (1, 2, 1.0)],
    "int": [(0, 1, 2), (1, 2, 1)],
    "zero_weight": [(0, 1, 0.0), (1, 2, 1.0)],
}
_CUT_SETS = {
    "all_nodes": ({0, 1, 2}, None),
    "with_absent_node": ({0, 1, 2, 7}, None),
    "one_side": ({0}, None),
    "zero_weight_cut": ({0}, {1}),
    "explicit": ({2}, {0}),
}


@needs_nx
@pytest.mark.parametrize("cls", ["Graph", "DiGraph"])
@pytest.mark.parametrize("edges", sorted(_CUT_EDGES))
@pytest.mark.parametrize("sets", sorted(_CUT_SETS))
@pytest.mark.parametrize("weight", [None, "weight"])
@pytest.mark.parametrize("fn", ["cut_size", "edge_expansion", "mixing_expansion", "normalized_cut_size", "conductance"])
def test_zero_cut_value_type_and_sign_match_networkx(cls, edges, sets, weight, fn):
    S, T = _CUT_SETS[sets]
    if cls == "DiGraph" and T is None:
        pytest.skip("networkx's directed cut_size raises on T=None (see above)")

    def outcome(lib):
        g = getattr(lib, cls)()
        g.add_weighted_edges_from(_CUT_EDGES[edges])
        try:
            value = getattr(lib, fn)(g, S, T, weight=weight)
        except Exception as exc:  # noqa: BLE001 - the raise is the answer
            return ("raise", type(exc).__name__)
        return (repr(value), type(value).__name__)

    assert outcome(fnx) == outcome(nx)
