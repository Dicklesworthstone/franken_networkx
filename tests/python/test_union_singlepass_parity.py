"""Parity for the single-pass union (graph-attr fix + faster construction).

br-unionsinglepass: union previously built via native _raw_union (drops ALL
attributes) + _rebuild_operator_output + a per-node/edge _copy_attrs_into walk.
That dropped the graph-level attribute dict entirely (`union(G, H).graph == {}`
instead of nx's merged `{**G.graph, **H.graph}`) and was ~11x slower than nx.
It now builds the union in one attributed construction pass.
"""

import networkx as nx

import franken_networkx as fnx

_NX = {
    "graph": nx.Graph,
    "digraph": nx.DiGraph,
    "multi": nx.MultiGraph,
    "multidi": nx.MultiDiGraph,
}
_FNX = {
    "graph": fnx.Graph,
    "digraph": fnx.DiGraph,
    "multi": fnx.MultiGraph,
    "multidi": fnx.MultiDiGraph,
}


def _mk(lib_map, kind, n, seed, off):
    G = lib_map[kind]()
    base = nx.connected_watts_strogatz_graph(n, 4, 0.3, seed=seed)
    G.add_nodes_from((x + off, {"c": x + off}) for x in base.nodes())
    for i, (u, v) in enumerate(base.edges()):
        G.add_edge(u + off, v + off, weight=i % 9)
        if "multi" in kind:
            G.add_edge(u + off, v + off, weight=99)
    G.graph["name"] = f"N{seed}"
    G.graph["s"] = seed
    return G


def _sig(R):
    head = (
        sorted(R.graph.items()),
        sorted((repr(n), tuple(sorted(d.items()))) for n, d in R.nodes(data=True)),
        R.is_directed(),
        R.is_multigraph(),
    )
    if R.is_multigraph():
        edges = sorted(
            (repr(u), repr(v), repr(k), tuple(sorted(d.items())))
            for u, v, k, d in R.edges(keys=True, data=True)
        )
    else:
        edges = sorted(
            (repr(u), repr(v), tuple(sorted(d.items())))
            for u, v, d in R.edges(data=True)
        )
    return head + (edges,)


def test_parity_all_graph_types():
    for kind in ("graph", "digraph", "multi", "multidi"):
        Gx = _mk(_NX, kind, 12, 3, 0)
        Hx = _mk(_NX, kind, 12, 7, 100)
        Gf = _mk(_FNX, kind, 12, 3, 0)
        Hf = _mk(_FNX, kind, 12, 7, 100)
        assert _sig(nx.union(Gx, Hx)) == _sig(fnx.union(Gf, Hf)), kind


def test_graph_attrs_preserved_h_wins():
    # Regression for the dropped graph-attr dict.
    Gf = fnx.Graph([(0, 1)])
    Hf = fnx.Graph([(2, 3)])
    Gf.graph.update({"name": "G", "shared": 1})
    Hf.graph.update({"name": "H", "shared": 2, "only_h": True})
    R = fnx.union(Gf, Hf)
    assert dict(R.graph) == {"name": "H", "shared": 2, "only_h": True}


def test_rename_path():
    Gx = _mk(_NX, "graph", 6, 1, 0)
    Hx = _mk(_NX, "graph", 6, 1, 0)
    Gf = _mk(_FNX, "graph", 6, 1, 0)
    Hf = _mk(_FNX, "graph", 6, 1, 0)
    assert _sig(nx.union(Gx, Hx, rename=("a-", "b-"))) == _sig(
        fnx.union(Gf, Hf, rename=("a-", "b-"))
    )


def test_non_disjoint_raises():
    Gf = fnx.Graph([(0, 1)])
    Hf = fnx.Graph([(1, 2)])
    try:
        fnx.union(Gf, Hf)
    except fnx.NetworkXError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected NetworkXError for overlapping node sets")


def test_type_mismatch_raises():
    try:
        fnx.union(fnx.Graph([(0, 1)]), fnx.DiGraph([(2, 3)]))
    except fnx.NetworkXError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected NetworkXError for directed/undirected mismatch")
