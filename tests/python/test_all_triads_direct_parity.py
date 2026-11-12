"""Parity for the direct-construction all_triads (no per-triad subgraph copy).

br-ctcg-triaddirect: `all_triads` built each 3-node induced subgraph with
`G.subgraph([i, j, k]).copy()`, routing through fnx's filtered-view +
materialize-copy machinery (~7x slower than networkx, 1960ms vs 271ms on
gnm(40, 200)). It now snapshots G's node/edge/graph attributes once and builds
each triad directly with add_nodes_from / add_edges_from. The yielded triads
(nodes, induced edges, and node/edge/graph attribute copies) are byte-identical
to networkx.
"""

import random

import networkx as nx

import franken_networkx as fnx


def _mk(n, m, seed, *, attr=False):
    DG = nx.gnm_random_graph(n, m, seed=seed, directed=True)
    if attr:
        rnd = random.Random(seed)
        for u, v in DG.edges():
            DG[u][v]["weight"] = rnd.randint(1, 9)
            DG[u][v]["c"] = "e"
        for node in DG.nodes():
            DG.nodes[node]["color"] = f"c{node}"
        DG.graph["name"] = "g"
        DG.graph["k"] = 7
    DGf = fnx.DiGraph()
    DGf.graph.update(DG.graph)
    DGf.add_nodes_from((node, dict(d)) for node, d in DG.nodes(data=True))
    DGf.add_edges_from((u, v, dict(d)) for u, v, d in DG.edges(data=True))
    return DG, DGf


def _sig(H):
    return (
        sorted(H.graph.items()),
        sorted((repr(n), tuple(sorted(d.items()))) for n, d in H.nodes(data=True)),
        sorted(
            (repr(u), repr(v), tuple(sorted(d.items())))
            for u, v, d in H.edges(data=True)
        ),
    )


def test_parity_matrix():
    for n, m, attr in [
        (20, 80, False),
        (25, 120, True),
        (15, 40, True),
        (10, 90, True),
        (3, 3, True),
        (2, 1, False),
        (8, 0, True),
    ]:
        DG, DGf = _mk(n, m, n + m, attr=attr)
        sx = [_sig(h) for h in nx.all_triads(DG)]
        sf = [_sig(h) for h in fnx.all_triads(DGf)]
        assert sx == sf, (n, m, attr)


def test_yielded_triads_are_independent_copies():
    # Mutating one triad's edge/node attrs must not affect the source graph
    # or other triads (the subgraph-copy contract).
    _, DGf = _mk(6, 20, 3, attr=True)
    triads = list(fnx.all_triads(DGf))
    before = {(u, v): dict(d) for u, v, d in DGf.edges(data=True)}
    for H in triads:
        for u, v in list(H.edges()):
            H[u][v]["weight"] = -999
        for node in H.nodes():
            H.nodes[node]["color"] = "MUT"
    after = {(u, v): dict(d) for u, v, d in DGf.edges(data=True)}
    assert before == after


def test_undirected_raises_not_implemented():
    G = fnx.Graph([(0, 1), (1, 2)])
    try:
        list(fnx.all_triads(G))
    except fnx.NetworkXNotImplemented:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected NetworkXNotImplemented for undirected input")


def test_triad_count_is_n_choose_3():
    import math

    _, DGf = _mk(12, 50, 9)
    assert len(list(fnx.all_triads(DGf))) == math.comb(12, 3)


# br-r37-c1-sx0id: nx yields G.subgraph(triplet).copy() - selfloops kept,
# successors in G's adjacency order, and a MultiDiGraph's triads are
# MultiDiGraphs with their parallel edges; triads_by_type keys come in first-
# occurrence order, a triad with a selfloop is not a triad (triad_type raises),
# and a MultiDiGraph triad is classified by len(G.edges()), parallel edges
# counted.
def _triad_summary(t):
    kw = {"keys": True} if t.is_multigraph() else {}
    return (type(t).__name__, list(t.nodes(data=True)), list(t.edges(data=True, **kw)), dict(t.graph))


def _triad_outcome(fn):
    try:
        return ("ok", fn())
    except Exception as exc:  # noqa: BLE001 - the raise is the answer
        return ("raise", type(exc).__name__, str(exc))


def test_triads_selfloops_parallel_edges_and_key_order_match_networkx():
    for seed in range(40):
        rng = random.Random(seed)
        n = rng.randint(3, 6)
        edges = [(rng.randrange(n), rng.randrange(n), {"w": rng.randint(0, 2)}) for _ in range(rng.randint(n, 3 * n))]
        if seed % 3:
            edges = [(u, v, d) for u, v, d in edges if u != v]
        for cls in ("DiGraph", "MultiDiGraph"):
            gf, gn = getattr(fnx, cls)(), getattr(nx, cls)()
            for g in (gf, gn):
                g.add_nodes_from((i, {"c": i}) for i in range(n))
                g.add_edges_from(edges)
                g.graph["k"] = seed
            assert [_triad_summary(t) for t in fnx.all_triads(gf)] == [
                _triad_summary(t) for t in nx.all_triads(gn)
            ], (seed, cls)
            assert _triad_outcome(
                lambda: [(k, [_triad_summary(t) for t in v]) for k, v in fnx.triads_by_type(gf).items()]
            ) == _triad_outcome(
                lambda: [(k, [_triad_summary(t) for t in v]) for k, v in nx.triads_by_type(gn).items()]
            ), (seed, cls)
