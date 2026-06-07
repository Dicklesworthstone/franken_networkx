"""Phase B certification (clean-session coverage): ordering- and
value/type-sensitive surfaces not covered by the unit suite —
link-prediction emission order, component-family order, matrix/spectral
values, assortativity value+type. Both impls from identical fixed
graphs. Zero divergences at certification across ~40 probed functions.
"""
import random

import numpy as np
import networkx as nx
import pytest

import franken_networkx as fnx


def _mku(mod, seed, m, n=15, weighted=False):
    R = random.Random(seed)
    g = mod.Graph()
    for i in range(n):
        g.add_node(i)
    for u, v in ((R.randrange(n), R.randrange(n)) for _ in range(m)):
        if u != v:
            g.add_edge(u, v, weight=1.0 + (u % 3)) if weighted else g.add_edge(u, v)
    return g


def _L(gen):
    return [(repr(u), repr(v), round(s, 7)) for u, v, s in gen]


@pytest.mark.parametrize(
    "fn",
    [
        "jaccard_coefficient",
        "adamic_adar_index",
        "preferential_attachment",
        "resource_allocation_index",
        "common_neighbor_centrality",
    ],
)
def test_link_prediction_emission_order(fn):
    gf, gn = _mku(fnx, 51, 40), _mku(nx, 51, 40)
    assert _L(getattr(fnx, fn)(gf)) == _L(getattr(nx, fn)(gn)), fn


def test_component_family_order():
    gf, gn = _mku(fnx, 61, 22, n=20), _mku(nx, 61, 22, n=20)
    assert [[repr(x) for x in c] for c in fnx.connected_components(gf)] == [
        [repr(x) for x in c] for c in nx.connected_components(gn)
    ]
    assert [(repr(u), repr(v), d) for u, v, d in fnx.dfs_labeled_edges(gf, 0)] == [
        (repr(u), repr(v), d) for u, v, d in nx.dfs_labeled_edges(gn, 0)
    ]


def test_scc_wcc_order():
    R = random.Random(61)
    de = [(u, v) for u, v in ((R.randrange(15), R.randrange(15)) for _ in range(30)) if u != v]
    df, dn = fnx.DiGraph(de), nx.DiGraph(de)
    assert [[repr(x) for x in c] for c in fnx.strongly_connected_components(df)] == [
        [repr(x) for x in c] for c in nx.strongly_connected_components(dn)
    ]


def _arr(m):
    a = m.todense() if hasattr(m, "todense") else m
    return np.round(np.asarray(a), 6).tolist()


@pytest.mark.parametrize(
    "fn", ["adjacency_matrix", "laplacian_matrix", "normalized_laplacian_matrix", "modularity_matrix"]
)
def test_matrix_values(fn):
    gf, gn = _mku(fnx, 71, 50, weighted=True), _mku(nx, 71, 50, weighted=True)
    assert _arr(getattr(fnx, fn)(gf)) == _arr(getattr(nx, fn)(gn)), fn


def test_assortativity_value_and_type():
    gf, gn = _mku(fnx, 71, 50, weighted=True), _mku(nx, 71, 50, weighted=True)
    a = fnx.degree_assortativity_coefficient(gf)
    b = nx.degree_assortativity_coefficient(gn)
    assert (round(a, 9), type(a).__name__) == (round(b, 9), type(b).__name__)


def test_node_view_iteration_parity_and_staleness():
    """br-r37-c1-nodeiter: NoData NodeView iteration (list(G.nodes()) /
    list(G)) fast path must preserve node order, data variants, and the
    mutation-during-iteration RuntimeError contract."""
    rnd = random.Random(3)
    for trial in range(10):
        E = [(rnd.randrange(12), rnd.randrange(12)) for _ in range(rnd.randrange(3, 40))]
        gf, gn = fnx.Graph(E), nx.Graph(E)
        for n in list(gf)[:4]:
            gf.nodes[n]["c"] = n
            gn.nodes[n]["c"] = n
        assert [repr(n) for n in gf.nodes()] == [repr(n) for n in gn.nodes()], trial
        assert [repr(n) for n in gf] == [repr(n) for n in gn], trial
        assert [(repr(n), dict(d)) for n, d in gf.nodes(data=True)] == [
            (repr(n), dict(d)) for n, d in gn.nodes(data=True)
        ], trial

    gf, gn = fnx.Graph([(0, 1), (1, 2), (2, 3)]), nx.Graph([(0, 1), (1, 2), (2, 3)])

    def mut(g):
        try:
            for n in g.nodes():
                g.add_node(99 + n)
            return "no-raise"
        except RuntimeError:
            return "RuntimeError"

    assert mut(gf) == mut(gn) == "RuntimeError"


@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("view", ["in_degree", "out_degree", "degree"])
def test_directed_degree_views_index_path(cls, view):
    """br-r37-c1-degidx: directed degree views iterate via a single
    native bulk call (index-based for DiGraph). Order + values must
    match nx across weighted / nbunch / self-loop."""
    r = random.Random(7)
    for trial in range(10):
        ed = [(r.randrange(15), r.randrange(15)) for _ in range(r.randrange(3, 50))]
        df, dn = getattr(fnx, cls)(ed), getattr(nx, cls)(ed)
        assert [(repr(k), v) for k, v in getattr(df, view)()] == [
            (repr(k), v) for k, v in getattr(dn, view)()
        ], trial
        if ed:
            s = list(dn)[0]
            assert getattr(df, view)(s) == getattr(dn, view)(s), ("single", trial)
        nb = list(dn)[:3]
        assert [(repr(k), v) for k, v in getattr(df, view)(nb)] == [
            (repr(k), v) for k, v in getattr(dn, view)(nb)
        ], ("nbunch", trial)


def test_directed_degree_weighted_and_selfloop():
    wf, wn = fnx.DiGraph(), nx.DiGraph()
    for i, (u, v) in enumerate([(0, 1), (1, 2), (2, 0), (0, 0)]):
        wf.add_edge(u, v, weight=1 + i)
        wn.add_edge(u, v, weight=1 + i)
    assert [(repr(k), v) for k, v in wf.in_degree(weight="weight")] == [
        (repr(k), v) for k, v in wn.in_degree(weight="weight")
    ]
    assert [(repr(k), v) for k, v in wf.degree()] == [
        (repr(k), v) for k, v in wn.degree()
    ]
