"""Post-w7nn3 delegation re-audit find: topological_generations
lexicographically sorted each generation (string order put "10" before
"2") instead of nx's node-iteration order (gen 0) / zero-reach order
(later gens), and displayed members as node-map objects instead of the
zeroing parent's succ-row object (discovery-object class).
"""

import random

import networkx as nx
import pytest

import franken_networkx as fnx


def _rr(gens):
    return [[repr(n) for n in gen] for gen in gens]


def test_no_lexicographic_string_sort():
    gn, gf = nx.DiGraph(), fnx.DiGraph()
    for g in (gn, gf):
        for i in range(14):
            g.add_edge("root", i)
    assert _rr(fnx.topological_generations(gf)) == _rr(nx.topological_generations(gn))


def test_zero_reach_order_within_generation():
    gn, gf = nx.DiGraph(), fnx.DiGraph()
    for g in (gn, gf):
        for e in [(0, 2), (1, 2), (0, 1), (2, 4), (2, 3), (3, 5), (4, 5), (0, 5)]:
            g.add_edge(*e)
    assert _rr(fnx.topological_generations(gf)) == _rr(nx.topological_generations(gn))


def test_multigraph_parallel_edge_decrement():
    gn, gf = nx.MultiDiGraph(), fnx.MultiDiGraph()
    for g in (gn, gf):
        g.add_edge(0, 1)
        g.add_edge(0, 1)
        g.add_edge(1, 2)
        g.add_edge(0, 2)
    assert _rr(fnx.topological_generations(gf)) == _rr(nx.topological_generations(gn))


def test_mixed_key_zeroing_parent_row_objects():
    gn, gf = nx.DiGraph(), fnx.DiGraph()
    for g in (gn, gf):
        g.add_node(28)
        g.add_edge(7, 28.0)
        g.add_edge(28.0, 5)
    assert _rr(fnx.topological_generations(gf)) == _rr(nx.topological_generations(gn))


def test_random_dag_corpus():
    rnd = random.Random(31)
    for trial in range(20):
        n = rnd.randrange(4, 16)
        gn, gf = nx.DiGraph(), fnx.DiGraph()
        for g in (gn, gf):
            g.add_nodes_from(range(n))
        for _ in range(rnd.randrange(3, 30)):
            u, v = rnd.randrange(n), rnd.randrange(n)
            if u < v:
                gn.add_edge(u, v)
                gf.add_edge(u, v)
        assert _rr(fnx.topological_generations(gf)) == _rr(
            nx.topological_generations(gn)
        ), trial


def test_cycle_raises_unfeasible():
    gf = fnx.DiGraph([(1, 2), (2, 1)])
    with pytest.raises(fnx.NetworkXUnfeasible):
        list(fnx.topological_generations(gf))
