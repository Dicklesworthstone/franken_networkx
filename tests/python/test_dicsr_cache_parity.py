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
