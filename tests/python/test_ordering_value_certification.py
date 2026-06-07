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


@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_set_node_attributes_bulk_parity(cls):
    """br-r37-c1-snabulk + 8wj2: native bulk set_node_attributes(dict,
    name) on ALL FOUR classes — missing nodes skipped, copy refreshes
    inner from the mirror, get_node_attributes reads it back."""
    r = random.Random(5)
    for trial in range(12):
        ed = [(r.randrange(12), r.randrange(12)) for _ in range(r.randrange(2, 40))]
        af, an = getattr(fnx, cls)(ed), getattr(nx, cls)(ed)
        vv = {k: (k * 2 if trial % 2 else f"s{k}") for k in range(0, 18, 2)}
        fnx.set_node_attributes(af, vv, "attr")
        nx.set_node_attributes(an, vv, "attr")
        ref = sorted((repr(n), repr(d.get("attr"))) for n, d in an.nodes(data=True))
        assert sorted((repr(n), repr(d.get("attr"))) for n, d in af.nodes(data=True)) == ref, trial
        assert sorted(
            (repr(n), repr(d.get("attr"))) for n, d in af.copy().nodes(data=True)
        ) == ref, ("copy", trial)
        assert sorted(
            (repr(k), repr(v)) for k, v in fnx.get_node_attributes(af, "attr").items()
        ) == sorted((repr(k), repr(v)) for k, v in nx.get_node_attributes(an, "attr").items()), trial

    gf2, gn2 = fnx.Graph([(0, 1)]), nx.Graph([(0, 1)])
    fnx.set_node_attributes(gf2, 5, "z")
    nx.set_node_attributes(gn2, 5, "z")
    assert dict(gf2.nodes(data=True)) == dict(gn2.nodes(data=True))


@pytest.mark.parametrize("cls", ["Graph", "DiGraph"])
def test_set_edge_attributes_bulk_parity(cls):
    """br-r37-c1-seabulk: native bulk set_edge_attributes(dict, name)
    must match nx AND remain visible to native kernels (the mirror is
    flushed to inner via the edges-dirty flag). Covers reversed key
    (undirected), missing edge skip, and dijkstra inner-sync."""
    r = random.Random(5)
    for trial in range(12):
        ed = [(u, v) for u, v in ((r.randrange(10), r.randrange(10)) for _ in range(r.randrange(3, 30))) if u != v]
        gf, gn = getattr(fnx, cls)(ed), getattr(nx, cls)(ed)
        el = list(gn.edges())
        vals = {e: (i + 1) * 1.5 for i, e in enumerate(el)}
        if not gn.is_directed() and el:
            vals[(el[0][1], el[0][0])] = 99.0  # reversed key (undirected)
        vals[(999, 998)] = 7.0  # missing edge -> skipped
        fnx.set_edge_attributes(gf, vals, "weight")
        nx.set_edge_attributes(gn, vals, "weight")
        assert sorted((repr(u), repr(v), d.get("weight")) for u, v, d in gf.edges(data=True)) == sorted(
            (repr(u), repr(v), d.get("weight")) for u, v, d in gn.edges(data=True)
        ), trial
        if el and gn.number_of_nodes() > 2:
            s = list(gn)[0]
            da = fnx.single_source_dijkstra_path_length(gf, s)
            db = nx.single_source_dijkstra_path_length(gn, s)
            assert {repr(k): round(v, 6) for k, v in da.items()} == {
                repr(k): round(v, 6) for k, v in db.items()
            }, ("dijkstra inner-sync", trial)
