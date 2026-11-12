"""Phase B certification: Laplacian/current-flow centralities (value +
python-float type) and pagerank/hits parameter variants. Zero
divergences.
"""
import random

import networkx as nx

import franken_networkx as fnx


def _mk_connected():
    R = random.Random(89)
    ue = [(u, v) for u, v in ((R.randrange(12), R.randrange(12)) for _ in range(40)) if u != v]
    gf, gn = fnx.Graph(ue), nx.Graph(ue)
    if not nx.is_connected(gn):
        comp = list(nx.connected_components(gn))
        for i in range(len(comp) - 1):
            a, b = next(iter(comp[i])), next(iter(comp[i + 1]))
            gf.add_edge(a, b)
            gn.add_edge(a, b)
    return gf, gn


def _D(d):
    return sorted((repr(k), round(float(v), 6), type(v).__name__) for k, v in d.items())


def test_current_flow_and_laplacian_centrality():
    gf, gn = _mk_connected()
    assert _D(nx.current_flow_betweenness_centrality(gf)) == _D(nx.current_flow_betweenness_centrality(gn))
    assert _D(nx.current_flow_closeness_centrality(gf)) == _D(nx.current_flow_closeness_centrality(gn))
    assert _D(nx.information_centrality(gf)) == _D(nx.information_centrality(gn))
    assert _D(nx.laplacian_centrality(gf)) == _D(nx.laplacian_centrality(gn))


def test_edge_current_flow_betweenness():
    gf, gn = _mk_connected()
    assert sorted(
        (min(repr(u), repr(v)), max(repr(u), repr(v)), round(val, 6))
        for (u, v), val in nx.edge_current_flow_betweenness_centrality(gf).items()
    ) == sorted(
        (min(repr(u), repr(v)), max(repr(u), repr(v)), round(val, 6))
        for (u, v), val in nx.edge_current_flow_betweenness_centrality(gn).items()
    )


def test_pagerank_variants_and_hits():
    R = random.Random(89)
    ue = [(u, v) for u, v in ((R.randrange(12), R.randrange(12)) for _ in range(40)) if u != v]
    df, dn = fnx.DiGraph(ue), nx.DiGraph(ue)
    pers = {i: (i + 1) for i in set(u for u, _ in ue) | set(v for _, v in ue)}

    def _PR(g, **kw):
        return sorted((repr(k), round(v, 6)) for k, v in nx.pagerank(g, **kw).items())

    assert _PR(df, personalization=pers) == _PR(dn, personalization=pers)
    assert _PR(df, dangling=pers) == _PR(dn, dangling=pers)
    assert _PR(df, alpha=0.5) == _PR(dn, alpha=0.5)

    def _H(g, idx):
        return sorted((repr(k), round(v, 6)) for k, v in nx.hits(g)[idx].items())

    assert _H(df, 0) == _H(dn, 0)
    assert _H(df, 1) == _H(dn, 1)
