"""Regression: native graph products handle self-loops.

br-r37-c1-prodself (cc): the native product fast path (_native_graph_product ->
_fnx.{cartesian,tensor,strong,lexicographic}_product_fast) bailed (returned None)
whenever EITHER factor had a self-loop, dropping the whole product to the ~4x-slower
Python construction (cartesian 0.25x / tensor 0.28x / strong 0.26x / lexicographic
0.18x vs nx with just one incidental self-loop).

The kernel already enumerates each factor's edges with ``v >= u`` (self-loop pairs
included), and the simple-graph builder de-duplicates the tensor/lexicographic
double-push of a self-loop-induced product edge (a simple Graph cannot hold a
parallel edge), so the native path is byte-exact with nx for self-loop inputs.
These lock that parity (the existing product parity tests used self-loop-free
factors, so the native self-loop path was never exercised).

Product parity is order-insensitive (node set + edge set, undirected endpoints
normalised), matching the rest of the product suite.
"""

import random

import networkx as nx
import pytest

import franken_networkx as fnx

_PRODUCTS = [
    ("cartesian", fnx.cartesian_product, nx.cartesian_product),
    ("tensor", fnx.tensor_product, nx.tensor_product),
    ("strong", fnx.strong_product, nx.strong_product),
    ("lexicographic", fnx.lexicographic_product, nx.lexicographic_product),
]


def _sig(P):
    nodes = sorted(map(str, P.nodes()))
    if P.is_directed():
        edges = sorted((str(a), str(b)) for a, b in P.edges())
    else:
        edges = sorted(tuple(sorted((str(a), str(b)))) for a, b in P.edges())
    return nodes, edges, P.number_of_nodes(), P.number_of_edges()


def _mk(mod, n, seed, directed):
    r = random.Random(seed)
    G = (mod.DiGraph if directed else mod.Graph)()
    G.add_nodes_from(range(n))
    es = set()
    for _ in range(r.randint(0, n * 2)):
        u, v = r.randrange(n), r.randrange(n)  # includes self-loops
        es.add((u, v) if directed else tuple(sorted((u, v))))
    G.add_edges_from(es)
    return G


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("name", [p[0] for p in _PRODUCTS])
def test_product_with_selfloops_matches_networkx(name, directed):
    pf, px = next((f, x) for n, f, x in _PRODUCTS if n == name)
    for seed in range(40):
        gf, gx = _mk(fnx, 6, seed, directed), _mk(nx, 6, seed, directed)
        hf, hx = _mk(fnx, 5, seed + 100, directed), _mk(nx, 5, seed + 100, directed)
        assert _sig(pf(gf, hf)) == _sig(px(gx, hx)), (name, directed, seed)


def test_explicit_selfloop_products():
    # G has a self-loop at 0; H is a path. Verify each product against nx exactly.
    for directed in (False, True):
        gf, gx = (fnx.DiGraph if directed else fnx.Graph)(), (nx.DiGraph if directed else nx.Graph)()
        hf, hx = (fnx.DiGraph if directed else fnx.Graph)(), (nx.DiGraph if directed else nx.Graph)()
        for g in (gf, gx):
            g.add_edges_from([(0, 1), (1, 2), (0, 0)])
        for h in (hf, hx):
            h.add_edges_from([("a", "b"), ("b", "b")])  # H also has a self-loop
        for name, pf, px in _PRODUCTS:
            assert _sig(pf(gf, hf)) == _sig(px(gx, hx)), (name, directed)


def test_selfloop_free_products_unaffected():
    gf, gx = fnx.path_graph(5), nx.path_graph(5)
    hf, hx = fnx.cycle_graph(4), nx.cycle_graph(4)
    for name, pf, px in _PRODUCTS:
        assert _sig(pf(gf, hf)) == _sig(px(gx, hx)), name
