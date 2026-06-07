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


def test_bellman_spfa_skip_heuristic():
    """br-r37-c1-86xx9 part 2: nx's SPFA skips a popped node's
    relaxations while any of its current predecessors is still queued,
    and keeps pred LISTS (equality appends) feeding that check. The
    pinned minimal repro: without the skip, node 0 was discovered at a
    stale distance nx never materializes, scrambling dict key order."""
    gf, gn = fnx.DiGraph(), nx.DiGraph()
    for u, v, w in [(3, 11, 1), (5, 0, 4), (3, 10, 4), (10, 11, 1), (2, 6, 1), (3, 1, 3), (11, 5, 4), (1, 2, 4), (3, 11, 7)]:
        gf.add_edge(u, v, weight=w)
        gn.add_edge(u, v, weight=w)
    a = list(dict(fnx.single_source_bellman_ford_path_length(gf, 3)).items())
    b = list(dict(nx.single_source_bellman_ford_path_length(gn, 3)).items())
    assert a == b

    rnd = random.Random(13)
    for trial in range(25):
        n = rnd.randrange(3, 22)
        gf, gn = (fnx.DiGraph(), nx.DiGraph()) if trial % 2 else (fnx.Graph(), nx.Graph())
        for _ in range(rnd.randrange(2, 60)):
            u, v = rnd.randrange(n), rnd.randrange(n)
            if u != v:
                w = rnd.choice([1, 2, 2.5, 3, 7])
                gf.add_edge(u, v, weight=w)
                gn.add_edge(u, v, weight=w)
        if not len(gn):
            continue
        s = next(iter(gn))
        a = [(repr(k), v, type(v).__name__) for k, v in fnx.single_source_bellman_ford_path_length(gf, s).items()]
        b = [(repr(k), v, type(v).__name__) for k, v in nx.single_source_bellman_ford_path_length(gn, s).items()]
        assert a == b, trial


def test_tree_lazy_mirrors_write_through():
    """d58s8 tree-assembly tier: trees are built with LAZY attr mirrors;
    the DiGraph view accessors must MATERIALIZE absent mirrors on access
    (a fresh unstored dict silently loses `t.nodes[n]['x'] = 1`)."""
    t = fnx.bfs_tree(fnx.DiGraph([(1, 2), (2, 3)]), 1)
    t.nodes[2]["x"] = 9
    assert dict(t.nodes[2]) == {"x": 9}
    t[1][2]["w"] = 5
    assert dict(t[1][2]) == {"w": 5}
    assert t.nodes.get(3) == {}
    t.nodes.get(3)["y"] = 4
    assert dict(t.nodes[3]) == {"y": 4}
    # weighted algorithm sees the write (mirror -> inner sync)
    import networkx as _nx

    tn = _nx.bfs_tree(_nx.DiGraph([(1, 2), (2, 3)]), 1)
    tn[1][2]["w"] = 5
    a = fnx.single_source_dijkstra_path_length(t, 1, weight="w")
    b = _nx.single_source_dijkstra_path_length(tn, 1, weight="w")
    assert [(repr(k), v) for k, v in a.items()] == [(repr(k), v) for k, v in b.items()]


def test_bellman_csr_negative_weights_and_cycle():
    """P1: SPFA on CSR — negatives still correct, cycle still raises."""
    gf, gn = fnx.DiGraph(), nx.DiGraph()
    for g in (gf, gn):
        g.add_edge(1, 2, weight=4)
        g.add_edge(1, 3, weight=1)
        g.add_edge(3, 2, weight=-2)
        g.add_edge(2, 4, weight=2)
    a = [(repr(k), v) for k, v in fnx.single_source_bellman_ford_path_length(gf, 1).items()]
    b = [(repr(k), v) for k, v in nx.single_source_bellman_ford_path_length(gn, 1).items()]
    assert a == b
    for g in (gf, gn):
        g.add_edge(4, 3, weight=-5)
    import pytest as _pytest

    with _pytest.raises(Exception) as ea:
        fnx.single_source_bellman_ford_path_length(gf, 1)
    with _pytest.raises(Exception) as eb:
        nx.single_source_bellman_ford_path_length(gn, 1)
    assert type(ea.value).__name__ == type(eb.value).__name__


def test_bfs_layers_directed_csr_port():
    """P1 final port: layered multi-source BFS on CSR — layer membership
    order byte-identical; descendants_at_distance rides it."""
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
        for srcs in ([s], [s, list(gn)[-1]]):
            a = [[repr(x) for x in layer] for layer in fnx.bfs_layers(gf, srcs)]
            b = [[repr(x) for x in layer] for layer in nx.bfs_layers(gn, srcs)]
            assert a == b, (trial, srcs)
        assert sorted(map(repr, fnx.descendants_at_distance(gf, s, 2))) == sorted(
            map(repr, nx.descendants_at_distance(gn, s, 2))
        ), trial


def test_edges_walk_index_native_orientation():
    """P2(b): edges_ordered walks adj_indices with integer dedup; the
    endpoint store is STRING-canonical while walk pairs are
    index-canonical — the normalization mismatch silently DROPPED
    edges whose orientations disagreed (e.g. '10' < '9' string-wise).
    Pin multi-digit node names + post-remove renumbering."""
    import networkx as _nx

    gn, gf = _nx.Graph(), fnx.Graph()
    for u, v in [(10, 9), (9, 2), (2, 10), (1, 10), (11, 3)]:
        gn.add_edge(u, v, w=u + v)
        gf.add_edge(u, v, w=u + v)
    a = [(repr(u), repr(v), dict(d)) for u, v, d in gf.edges(data=True)]
    b = [(repr(u), repr(v), dict(d)) for u, v, d in gn.edges(data=True)]
    assert a == b
    gn.remove_node(9)
    gf.remove_node(9)
    assert [(repr(u), repr(v)) for u, v in gf.edges()] == [(repr(u), repr(v)) for u, v in gn.edges()]


def test_ctor_bulk_absorb_parity():
    """d58s8 ctor lever 2: __new__ batches the edge-tuple stream through
    extend_edges_with_attrs_unrecorded — display objects (as-passed
    keys, z6uka row objects), dup attr merges, mixed keys, self-loop
    float/int display, interleaved-flush order all preserved."""
    import networkx as _nx

    for data in (
        [(0, 1), (1, 2), (2, 0)],
        [(0, 1, {"w": 2}), (1, 2, {"w": 3})],
        [(0, 1, {"a": 1}), (0, 1, {"b": 2}), (1, 0, {"a": 9})],
        [(28.0, 7), (7, "s"), ("s", 28)],
        [(12.0, 12), (12, 13)],
        [(0, 1, {}), (1, 2, {})],
        [("a", "b"), ("b", "c")],
    ):
        gf, gn = fnx.Graph(data), _nx.Graph(data)
        assert [repr(x) for x in gf] == [repr(x) for x in gn], data
        assert [(repr(u), repr(v), dict(d)) for u, v, d in gf.edges(data=True)] == [
            (repr(u), repr(v), dict(d)) for u, v, d in gn.edges(data=True)
        ], data
        assert {repr(n): [repr(x) for x in gf[n]] for n in gf} == {
            repr(n): [repr(x) for x in gn[n]] for n in gn
        }, data


def test_digraph_ctor_bulk_absorb_and_get_edge_data_lazy():
    """Directed twin of the ctor bulk absorb + the lazy-mirror contract
    hole it exposed: get_edge_data gated on MIRROR presence, returning
    the default for existing attr-less edges (broke subgraph-view
    copy). Now gates on the inner edge and materializes."""
    import networkx as _nx

    for data in (
        [(0, 1), (1, 2), (2, 0)],
        [(0, 1, {"w": 2}), (1, 2, {"w": 3})],
        [(0, 1), (1, 0)],
        [(28.0, 7), (7, "s")],
    ):
        gf, gn = fnx.DiGraph(data), _nx.DiGraph(data)
        assert [repr(x) for x in gf] == [repr(x) for x in gn], data
        assert [(repr(u), repr(v), dict(d)) for u, v, d in gf.edges(data=True)] == [
            (repr(u), repr(v), dict(d)) for u, v, d in gn.edges(data=True)
        ], data
        assert {repr(n): [repr(x) for x in gf.pred[n]] for n in gf} == {
            repr(n): [repr(x) for x in gn.pred[n]] for n in gn
        }, data
    g = fnx.DiGraph([(1, 2)])
    assert g.get_edge_data(1, 2) == {}
    assert g.get_edge_data(2, 1) is None
    import copy

    sv = g.subgraph([1, 2])
    assert sorted(map(repr, copy.copy(sv))) == ["1", "2"]

    generator_graph = fnx.DiGraph(iter([(0, 1), (1, 2)]))
    assert generator_graph.size(weight="w") == 2.0
    out_edge = next(iter(generator_graph.edges(data=True)))
    out_edge[2]["out"] = 7
    assert dict(generator_graph[0][1]) == {"out": 7}
    assert generator_graph.size(weight="out") == 8.0
    in_edge = next(iter(generator_graph.in_edges(data=True)))
    in_edge[2]["in"] = 11
    assert dict(generator_graph.get_edge_data(0, 1)) == {"out": 7, "in": 11}


def test_add_edges_from_global_attr_batch():
    """d58s8: global **attr now batches (was the 7x residual). nx merge
    order: datadict.update(attr) FIRST, per-edge dd overrides; existing
    edges update."""
    import networkx as _nx

    for data, gattr in (
        ([(0, 1), (1, 2)], {"weight": 5}),
        ([(0, 1, {"weight": 9}), (1, 2)], {"weight": 5}),
        ([(0, 1, {"a": 1}), (1, 2, {"b": 2})], {"c": 3}),
        ([(0, 1, {"a": 1}), (0, 1, {"b": 2})], {"c": 3}),
    ):
        gf, gn = fnx.Graph(), _nx.Graph()
        for g in (gf, gn):
            g.add_edge(0, 1, pre=1)
            g.add_edges_from(data, **gattr)
        assert [(repr(u), repr(v), sorted(d.items())) for u, v, d in gf.edges(data=True)] == [
            (repr(u), repr(v), sorted(d.items())) for u, v, d in gn.edges(data=True)
        ], (data, gattr)


def test_integer_side_removal_parity():
    """P2(c) slice 1: remove_node/remove_nodes_from filter edges via
    endpoint INDICES and rebuild adj_indices through an old->new remap
    (no String hashing). Rows, attrs, and post-removal traversal must
    survive the renumbering."""
    import networkx as _nx

    rnd = random.Random(31)
    for trial in range(15):
        n = rnd.randrange(4, 30)
        gn, gf = _nx.Graph(), fnx.Graph()
        for _ in range(rnd.randrange(3, 80)):
            u, v = rnd.randrange(n), rnd.randrange(n)
            gn.add_edge(u, v, w=u)
            gf.add_edge(u, v, w=u)
        if len(gn) < 3:
            continue
        nodes = list(gn)
        gf.remove_node(nodes[0])
        gn.remove_node(nodes[0])
        batch = nodes[1 : len(nodes) // 2] + [99999]
        gf.remove_nodes_from(batch)
        gn.remove_nodes_from(batch)
        assert [repr(x) for x in gf] == [repr(x) for x in gn], trial
        assert [(repr(u), repr(v), dict(d)) for u, v, d in gf.edges(data=True)] == [
            (repr(u), repr(v), dict(d)) for u, v, d in gn.edges(data=True)
        ], trial
        assert {repr(x): [repr(y) for y in gf[x]] for x in gf} == {
            repr(x): [repr(y) for y in gn[x]] for x in gn
        }, trial


def test_digraph_eager_index_rows_oracle():
    """DiGraph flip P1: eager succ/pred index rows maintained by every
    writer; the oracle compares them against the String rows (order
    included) through mixed mutation sequences + copy/pickle/reverse/
    round-trip."""
    import pickle

    rnd = random.Random(41)
    for trial in range(15):
        n = rnd.randrange(4, 25)
        gf = fnx.DiGraph()
        for _ in range(rnd.randrange(10, 80)):
            r = rnd.random()
            if r < 0.5:
                gf.add_edge(rnd.randrange(n), rnd.randrange(n))
            elif r < 0.62 and len(gf) > 2:
                gf.remove_node(rnd.choice(list(gf)))
            elif r < 0.75 and gf.number_of_edges() > 1:
                gf.remove_edge(*rnd.choice(list(gf.edges())))
            elif r < 0.85:
                gf.remove_nodes_from([rnd.randrange(n) for _ in range(3)])
            else:
                gf.add_node(rnd.randrange(n, n + 5))
        assert gf._debug_index_rows_consistent(), trial
        assert pickle.loads(pickle.dumps(gf))._debug_index_rows_consistent(), trial
        assert gf.copy()._debug_index_rows_consistent(), trial
        assert gf.reverse(copy=True)._debug_index_rows_consistent(), trial


def test_edges_map_index_keys_rekey_on_removal():
    """d58s8 edges-map flip: Graph.edges keyed by index-canonical
    (min,max) pairs — node removal REKEYS survivors. has_edge/attrs/
    weighted-algo correctness through heavy renumbering."""
    import networkx as _nx

    rnd = random.Random(61)
    for trial in range(12):
        n = rnd.randrange(4, 25)
        gf, gn = fnx.Graph(), _nx.Graph()
        for _ in range(rnd.randrange(10, 90)):
            r = rnd.random()
            if r < 0.5:
                u, v = rnd.randrange(n), rnd.randrange(n)
                gf.add_edge(u, v, w=u + v)
                gn.add_edge(u, v, w=u + v)
            elif r < 0.7 and len(gn) > 2:
                x = rnd.choice(list(gn))
                gf.remove_node(x)
                gn.remove_node(x)
            elif r < 0.85:
                batch = [rnd.randrange(n) for _ in range(3)]
                gf.remove_nodes_from(batch)
                gn.remove_nodes_from(batch)
            elif gn.number_of_edges() > 1:
                e = rnd.choice(list(gn.edges()))
                gf.remove_edge(*e)
                gn.remove_edge(*e)
        assert [(repr(u), repr(v), dict(d)) for u, v, d in gf.edges(data=True)] == [
            (repr(u), repr(v), dict(d)) for u, v, d in gn.edges(data=True)
        ], trial
        for u in list(gn)[:5]:
            for v in list(gn)[:5]:
                assert gf.has_edge(u, v) == gn.has_edge(u, v), (trial, u, v)
