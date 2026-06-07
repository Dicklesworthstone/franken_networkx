"""br-r37-c1-d58s8 P1: DiGraph::csr() revision-keyed CSR cache + the
first ported kernel (sssp_len directed). The cache derives from the
String maps (never eagerly maintained — the I5 renumbering hazard
cannot apply) and invalidates implicitly via revision bumps."""

import random

import networkx as nx

import franken_networkx as fnx


def test_random_digraph_corpus_with_cutoffs():
    rnd = random.Random(3)
    for trial in range(20):
        n = rnd.randrange(3, 30)
        gn, gf = nx.DiGraph(), fnx.DiGraph()
        for _ in range(rnd.randrange(2, 80)):
            u, v = rnd.randrange(n), rnd.randrange(n)
            if u != v:
                gn.add_edge(u, v)
                gf.add_edge(u, v)
        if not len(gn):
            continue
        s = next(iter(gn))
        for cutoff in (None, 2):
            a = [(repr(k), v) for k, v in fnx.single_source_shortest_path_length(gf, s, cutoff=cutoff).items()]
            b = [(repr(k), v) for k, v in nx.single_source_shortest_path_length(gn, s, cutoff=cutoff).items()]
            assert a == b, (trial, cutoff)


def test_cache_invalidation_through_mutations():
    """Query (cache built) -> add_edge -> remove_node (index
    RENUMBERING) -> add_edge -> re-query: revision bumps must
    invalidate; stale CSR indices would mis-route."""
    gf, gn = fnx.DiGraph([(1, 2), (2, 3)]), nx.DiGraph([(1, 2), (2, 3)])
    _ = fnx.single_source_shortest_path_length(gf, 1)
    for g in (gf, gn):
        g.add_edge(3, 4)
        g.remove_node(2)
        g.add_edge(1, 4)
    a = [(repr(k), v) for k, v in fnx.single_source_shortest_path_length(gf, 1).items()]
    b = [(repr(k), v) for k, v in nx.single_source_shortest_path_length(gn, 1).items()]
    assert a == b


def test_mixed_key_discovery_objects_preserved():
    gm, gx = fnx.DiGraph(), nx.DiGraph()
    for g in (gm, gx):
        g.add_node(28)
        g.add_edge(7, 28.0)
        g.add_edge(28.0, 5)
    a = [(repr(k), v) for k, v in fnx.single_source_shortest_path_length(gm, 7).items()]
    b = [(repr(k), v) for k, v in nx.single_source_shortest_path_length(gx, 7).items()]
    assert a == b


def test_bfs_edges_directed_csr_port():
    """P1(b): bfs_edges_directed/_reverse on CSR — consumers
    (bfs_tree, descendants, sp(target)) byte-identical."""
    rnd = random.Random(3)
    for trial in range(15):
        n = rnd.randrange(3, 30)
        gn, gf = nx.DiGraph(), fnx.DiGraph()
        for _ in range(rnd.randrange(2, 80)):
            u, v = rnd.randrange(n), rnd.randrange(n)
            if u != v:
                gn.add_edge(u, v)
                gf.add_edge(u, v)
        if not len(gn):
            continue
        s = next(iter(gn))
        for kw in ({}, {"depth_limit": 2}, {"reverse": True}):
            assert [(repr(u), repr(v)) for u, v in fnx.bfs_edges(gf, s, **kw)] == [
                (repr(u), repr(v)) for u, v in nx.bfs_edges(gn, s, **kw)
            ], (trial, kw)
        assert [repr(x) for x in fnx.bfs_tree(gf, s)] == [repr(x) for x in nx.bfs_tree(gn, s)], trial


def test_dfs_edges_directed_csr_port():
    """P1(c): dfs_edges_directed on CSR — reverse-push stack discipline
    preserved; consumers (tree/preorder/postorder/preds/succs)
    byte-identical."""
    rnd = random.Random(3)
    for trial in range(15):
        n = rnd.randrange(3, 30)
        gn, gf = nx.DiGraph(), fnx.DiGraph()
        for _ in range(rnd.randrange(2, 80)):
            u, v = rnd.randrange(n), rnd.randrange(n)
            if u != v:
                gn.add_edge(u, v)
                gf.add_edge(u, v)
        if not len(gn):
            continue
        s = next(iter(gn))
        for kw in ({}, {"depth_limit": 2}, {"depth_limit": 1}):
            assert [(repr(u), repr(v)) for u, v in fnx.dfs_edges(gf, s, **kw)] == [
                (repr(u), repr(v)) for u, v in nx.dfs_edges(gn, s, **kw)
            ], (trial, kw)
        assert [repr(x) for x in fnx.dfs_preorder_nodes(gf, s)] == [
            repr(x) for x in nx.dfs_preorder_nodes(gn, s)
        ], trial
        assert [repr(x) for x in fnx.dfs_postorder_nodes(gf, s)] == [
            repr(x) for x in nx.dfs_postorder_nodes(gn, s)
        ], trial


def test_dijkstra_directed_csr_port():
    """P1(d): both directed dijkstra kernels (length-only + the FULL
    variant the shared binding calls) on CSR — finalize order (k9q6q),
    tie-breaks, and path reconstruction byte-identical."""
    rnd = random.Random(3)
    for trial in range(15):
        n = rnd.randrange(3, 30)
        gn, gf = nx.DiGraph(), fnx.DiGraph()
        for _ in range(rnd.randrange(2, 80)):
            u, v = rnd.randrange(n), rnd.randrange(n)
            if u == v:
                continue
            w = rnd.choice([1, 2.5, 0.1, 7, 1])
            gn.add_edge(u, v, weight=w)
            gf.add_edge(u, v, weight=w)
        if not len(gn):
            continue
        s = next(iter(gn))
        a = [(repr(k), v) for k, v in fnx.single_source_dijkstra_path_length(gf, s).items()]
        b = [(repr(k), v) for k, v in nx.single_source_dijkstra_path_length(gn, s).items()]
        assert a == b, trial
        da, pa = fnx.single_source_dijkstra(gf, s)
        db, pb = nx.single_source_dijkstra(gn, s)
        assert [(repr(k), v) for k, v in da.items()] == [(repr(k), v) for k, v in db.items()], trial
        assert [(repr(k), [repr(x) for x in p]) for k, p in pa.items()] == [
            (repr(k), [repr(x) for x in p]) for k, p in pb.items()
        ], trial


def test_multi_source_dijkstra_directed_finalize_order():
    """br-r37-c1-86xx9: the directed multi-source kernel emitted
    node-index order (the undirected twin had the k9q6q finalize
    treatment; this one was missed) — equal-distance tie groups came
    out in insertion order instead of nx's heap push-seq order."""
    rnd = random.Random(5)
    for trial in range(25):
        n = rnd.randrange(3, 20)
        gn, gf = (nx.DiGraph(), fnx.DiGraph()) if trial % 3 else (nx.Graph(), fnx.Graph())
        for _ in range(rnd.randrange(2, 50)):
            u, v = rnd.randrange(n), rnd.randrange(n)
            if u == v:
                continue
            w = rnd.randrange(1, 9) if trial % 2 == 0 else rnd.choice([1, 2.5, 3])
            gn.add_edge(u, v, weight=w)
            gf.add_edge(u, v, weight=w)
        if not len(gn):
            continue
        s = next(iter(gn))
        for srcs in ({s}, [s, list(gn)[-1]]):
            a = [(repr(k), v, type(v).__name__) for k, v in fnx.multi_source_dijkstra_path_length(gf, srcs).items()]
            b = [(repr(k), v, type(v).__name__) for k, v in nx.multi_source_dijkstra_path_length(gn, srcs).items()]
            assert a == b, (trial, srcs)
