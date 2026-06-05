"""br-r37-c1-z6uka (phase 1, Graph): per-adjacency-row display-key parity.

nx's `_adj[u]` dict keeps the py object passed in the call that CREATED
each cell — which can differ from the `_node` (global first-wins) object
when hash-equal keys of different types are mixed (28 vs 28.0 vs True).
PyGraph now carries a sparse `adj_py_keys` override map (empty for every
uniform-key graph) consulted by adjacency/neighbors/edge-tuple rendering;
the batch paths bail to the per-edge add_edge on mixed-display input.
"""

import random

import networkx as nx

import franken_networkx as fnx


def _canon(g):
    return (
        [repr(n) for n in g],
        [(repr(u), repr(v), dict(d)) for u, v, d in g.edges(data=True)],
        {repr(x): [repr(y) for y in g[x]] for x in g},
    )


def _pair(build):
    gn, gf = nx.Graph(), fnx.Graph()
    build(gn)
    build(gf)
    return gn, gf


def test_shrunk_repro_per_edge():
    gn, gf = _pair(lambda g: (g.add_edge(36, 16.0, weight=1), g.add_edge("n58", 16, weight=2)))
    assert _canon(gf) == _canon(gn)
    assert [repr(x) for x in gf.neighbors("n58")] == ["16"]


def test_selfloop_mixed_types():
    # nx: the reverse adj assignment cannot replace the hash-equal key —
    # add_edge(12.0, 12) renders the self-loop as (12, 12).
    gn, gf = _pair(lambda g: g.add_edges_from([(12, 28.0, {}), (12.0, 12)]))
    assert _canon(gf) == _canon(gn)


def test_batch_paths_bail_and_match():
    edges = [(36, 16.0), ("n58", 16)] + [(f"k{i}", f"k{i + 1}") for i in range(10)]
    gn, gf = _pair(lambda g: g.add_edges_from(edges))
    assert _canon(gf) == _canon(gn)


def test_random_mixed_corpus():
    rnd = random.Random(20260605)
    for trial in range(25):
        edges = []
        for _ in range(rnd.choice([5, 30, 120])):
            def mk():
                return rnd.choice(
                    [rnd.randrange(40), float(rnd.randrange(20)), f"s{rnd.randrange(40)}", bool(rnd.randrange(2))]
                )
            if rnd.random() < 0.5:
                edges.append((mk(), mk()))
            else:
                edges.append((mk(), mk(), {"w": rnd.random()}))
        gn, gf = nx.Graph(), fnx.Graph()
        gn.add_edges_from(edges)
        gf.add_edges_from(edges)
        assert _canon(gf) == _canon(gn), trial


def test_removal_and_readd_resets_row_object():
    gn, gf = _pair(
        lambda g: (g.add_edge(7, 8.0), g.remove_edge(7, 8.0), g.add_edge(8, 7.0))
    )
    assert _canon(gf) == _canon(gn)


def test_copy_subgraph_propagate_overrides():
    gn, gf = _pair(lambda g: (g.add_edge(36, 16.0), g.add_edge("n58", 16)))
    assert _canon(gf.copy()) == _canon(gn.copy())
    assert _canon(gf.subgraph(["n58", 16]).copy()) == _canon(gn.subgraph(["n58", 16]).copy())


def test_remove_node_clears_overrides():
    gn, gf = _pair(
        lambda g: (g.add_edge(36, 16.0), g.add_edge("n58", 16), g.remove_node(16.0))
    )
    assert _canon(gf) == _canon(gn)
    # re-add with the other type
    gn.add_edge("n58", 16.0)
    gf.add_edge("n58", 16.0)
    assert _canon(gf) == _canon(gn)


def test_uniform_graphs_unchanged():
    rnd = random.Random(7)
    for keyfn in (lambda: rnd.randrange(50), lambda: f"s{rnd.randrange(50)}"):
        gn, gf = nx.Graph(), fnx.Graph()
        for _ in range(150):
            u, v = keyfn(), keyfn()
            gn.add_edge(u, v, w=1)
            gf.add_edge(u, v, w=1)
        assert _canon(gf) == _canon(gn)
