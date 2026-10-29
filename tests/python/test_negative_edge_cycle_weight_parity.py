"""Parity for negative_edge_cycle non-string weight argument.

Bead br-r37-c1-f0i2s.

The Rust binding exposed by ``_raw_negative_edge_cycle`` declares
``weight: str`` so passing ``weight=5`` (or ``None``, or any other
non-string) raises::

    TypeError: argument 'weight': 'int' object is not an instance of 'str'

…before the algorithm runs.  nx accepts any hashable as ``weight``
(it's used as an attribute key on edge-data dicts; non-string keys
silently fall back to the unweighted-default-of-1).

This is the same drift class as br-r37-c1-blu7u (which patched
the central dijkstra / bellman_ford / floyd_warshall / astar
delegation gates) — but ``negative_edge_cycle`` has its own gate
``_should_delegate_negative_edge_cycle_to_networkx`` that was
missed in that round.
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

NONSTRING_WEIGHTS = [
    pytest.param(5, id="int"),
    pytest.param(1.5, id="float"),
    pytest.param(b"weight", id="bytes"),
    pytest.param(("w",), id="tuple"),
    pytest.param(None, id="None"),
]


@needs_nx
@pytest.mark.parametrize("w", NONSTRING_WEIGHTS)
def test_negative_edge_cycle_undirected_nonstring_weight_matches_nx(w):
    """Undirected path: gate now routes non-string weight to nx;
    no negative cycle is found because nx falls back to default-1
    weights and the graph has positive edges."""
    G = fnx.Graph()
    G.add_weighted_edges_from([(0, 1, -1), (1, 2, 1)])
    GX = nx.Graph()
    GX.add_weighted_edges_from([(0, 1, -1), (1, 2, 1)])
    assert fnx.negative_edge_cycle(G, weight=w) == nx.negative_edge_cycle(GX, weight=w)


@needs_nx
@pytest.mark.parametrize("w", NONSTRING_WEIGHTS)
def test_negative_edge_cycle_directed_nonstring_weight_matches_nx(w):
    """Directed path: same — non-string weight delegates to nx."""
    DG = fnx.DiGraph()
    DG.add_weighted_edges_from([(0, 1, -1), (1, 2, -1), (2, 0, -1)])
    DGX = nx.DiGraph()
    DGX.add_weighted_edges_from([(0, 1, -1), (1, 2, -1), (2, 0, -1)])
    assert fnx.negative_edge_cycle(DG, weight=w) == nx.negative_edge_cycle(DGX, weight=w)


# ---------------------------------------------------------------------------
# Regressions — string and callable weights unchanged
# ---------------------------------------------------------------------------

@needs_nx
def test_negative_edge_cycle_string_weight_unchanged():
    G = fnx.Graph()
    G.add_weighted_edges_from([(0, 1, -1), (1, 2, 1)])
    GX = nx.Graph()
    GX.add_weighted_edges_from([(0, 1, -1), (1, 2, 1)])
    assert fnx.negative_edge_cycle(G, weight="weight") == nx.negative_edge_cycle(GX, weight="weight")


@needs_nx
def test_negative_edge_cycle_callable_weight_unchanged():
    G = fnx.Graph()
    G.add_weighted_edges_from([(0, 1, -1), (1, 2, 1)])
    GX = nx.Graph()
    GX.add_weighted_edges_from([(0, 1, -1), (1, 2, 1)])
    f = fnx.negative_edge_cycle(G, weight=lambda u, v, d: d.get("weight", 1.0))
    n = nx.negative_edge_cycle(GX, weight=lambda u, v, d: d.get("weight", 1.0))
    assert f == n


@needs_nx
def test_negative_edge_cycle_real_cycle_undirected_unchanged():
    """Sanity: real undirected negative-cycle graph still detected."""
    G = fnx.Graph()
    G.add_weighted_edges_from([(0, 1, -1), (1, 2, -1), (0, 2, -1)])
    GX = nx.Graph()
    GX.add_weighted_edges_from([(0, 1, -1), (1, 2, -1), (0, 2, -1)])
    assert fnx.negative_edge_cycle(G, weight="weight") == nx.negative_edge_cycle(GX, weight="weight")


@needs_nx
@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("sign", ["positive", "negative"])
@pytest.mark.parametrize("weight", ["weight", "callable"])
def test_negative_edge_cycle_answers_on_every_class(cls, sign, weight):
    """The undirected branch fed the multigraph weight function one parallel
    edge's attr dict instead of G[u][v]'s keydict, so an undirected MultiGraph
    raised AttributeError ('float' object has no attribute 'get')."""
    last = -4.0 if sign == "negative" else 4.0
    edges = [(0, 1, 1.5), (1, 2, 2.0), (2, 0, 3.0), (2, 3, last)]
    outcomes = {}
    for name, lib in (("nx", nx), ("fnx", fnx)):
        graph = getattr(lib, cls)()
        graph.add_weighted_edges_from(edges)
        if weight == "callable":
            # nx passes G[u][v]: the keydict on a multigraph. .get(..., 1) as
            # nx's own weight functions do - its helper edges carry no weight.
            if graph.is_multigraph():
                arg = lambda u, v, d: min(attrs.get("weight", 1) for attrs in d.values())  # noqa: E731
            else:
                arg = lambda u, v, d: d.get("weight", 1)  # noqa: E731
        else:
            arg = weight
        try:
            outcomes[name] = ("ok", lib.negative_edge_cycle(graph, weight=arg))
        except Exception as exc:  # noqa: BLE001 - the raise is the defect
            outcomes[name] = ("raise", type(exc).__name__)
    assert outcomes["fnx"] == outcomes["nx"]


# The native search (simple Graph / DiGraph, string weight, numbers the f64
# search adds exactly) against networkx on random graphs: the answer is a
# bool, so it must agree whatever detector found it. The directed graphs used
# to run an in-process SPFA without networkx's early exit (0.12x networkx).
def _random_twins(seed):
    import random

    r = random.Random(seed)
    n = r.choice((5, 12, 40))
    directed = seed % 3 != 0
    kind = r.choice(["int", "float", "mixed", "missing", "mostly_positive"])

    def weight():
        if kind == "int":
            return r.randint(-3, 9)
        if kind == "float":
            return r.choice([-1.5, 0.5, 2.25, 4.0, -0.25])
        if kind == "mixed":
            return r.choice([-1, 2.5, 3, -0.5])
        if kind == "missing":
            return None if r.random() < 0.5 else r.randint(-1, 5)
        return r.randint(-1, 20)

    edges = []
    for _ in range(r.choice((n, 2 * n, 4 * n))):
        w = weight()
        edges.append((r.randrange(n), r.randrange(n), {} if w is None else {"weight": w}))
    graphs = []
    for lib in (fnx, nx):
        g = (lib.DiGraph if directed else lib.Graph)()
        g.add_nodes_from(range(n))
        g.add_edges_from(edges)
        graphs.append(g)
    return graphs


@pytest.mark.parametrize("seed", range(120))
def test_negative_edge_cycle_matches_networkx_on_random_graphs(seed):
    fg, ng = _random_twins(seed)
    assert fnx.negative_edge_cycle(fg) == nx.negative_edge_cycle(ng)


@pytest.mark.parametrize(
    "value",
    [float("nan"), float("inf"), float("-inf"), "-3", 2**60, -(2**60), -(2**70)],
)
def test_weights_the_native_search_cannot_add_keep_networkx_answer(value):
    edges = [(0, 1, {"weight": 1}), (1, 2, {"weight": value}), (2, 0, {"weight": 1})]
    for directed in (True, False):
        fg = (fnx.DiGraph if directed else fnx.Graph)(edges)
        ng = (nx.DiGraph if directed else nx.Graph)(edges)
        try:
            want = ("ok", nx.negative_edge_cycle(ng))
        except Exception as exc:  # noqa: BLE001 - the exception type is the answer
            want = ("raise", type(exc).__name__)
        try:
            got = ("ok", fnx.negative_edge_cycle(fg))
        except Exception as exc:  # noqa: BLE001
            got = ("raise", type(exc).__name__)
        assert got == want, (directed, value)


@pytest.mark.parametrize("kind", ["Fraction", "Decimal"])
def test_an_exact_zero_cycle_f64_would_round_negative_keeps_networkx_answer(kind):
    # 3/10 - 1/10 - 2/10 is exactly 0, so networkx finds no negative cycle; added
    # as f64 the same cycle comes out at about -2.8e-17. The native search adds
    # in f64, so these weights must stay on the exact route.
    from decimal import Decimal
    from fractions import Fraction

    exact = Fraction if kind == "Fraction" else (lambda p, q: Decimal(p) / Decimal(q))
    edges = [
        (0, 1, {"weight": exact(3, 10)}),
        (1, 2, {"weight": exact(-1, 10)}),
        (2, 0, {"weight": exact(-2, 10)}),
    ]
    fg, ng = fnx.DiGraph(edges), nx.DiGraph(edges)
    assert fnx.negative_edge_cycle(fg) == nx.negative_edge_cycle(ng)


def test_the_directed_answer_comes_from_the_native_search(monkeypatch):
    # A planted fault in the native route must show: the tests above reach it.
    import franken_networkx as package

    fg = fnx.DiGraph([(0, 1, {"weight": -2}), (1, 0, {"weight": 1})])
    monkeypatch.setattr(package, "_raw_negative_edge_cycle", lambda G, weight: "native")
    assert fnx.negative_edge_cycle(fg) == "native"
