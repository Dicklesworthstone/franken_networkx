"""Parity for vectorized numeric/attribute assortativity coefficients.

br-assortfast: numeric_assortativity_coefficient and attribute_assortativity_
coefficient went through attribute_mixing_matrix's slow node_attribute_xy iterator
(~2.3x slower than networkx). The numeric coefficient is the Pearson correlation of
the attribute values across edges (order-invariant); the categorical coefficient
((trace - sum(M@M)) / (1 - ...)) is invariant to the category->index mapping. So
for the common case (undirected simple graph, no self-loops, nodes=None) both are
computed in one vectorized pass from the native edge endpoint index arrays
(adjacency_default_order_index_arrays). Directed / multigraph / self-loop / nodes-
subset / nx-typed inputs fall back to the exact path. Results match networkx to
float tolerance; fnx goes from ~2.3x slower to ~2x FASTER.
"""

import math
import random

import networkx as nx

import franken_networkx as fnx


def _cp(G, directed=False, multi=False):
    if multi:
        F = fnx.MultiDiGraph() if directed else fnx.MultiGraph()
    else:
        F = fnx.DiGraph() if directed else fnx.Graph()
    F.add_nodes_from(G.nodes(data=True))
    F.add_edges_from(G.edges(keys=True, data=True) if multi else G.edges(data=True))
    return F


def _close(a, b, tol=1e-7):
    return (math.isnan(a) and math.isnan(b)) or abs(a - b) <= tol


def test_numeric_and_attribute_match_networkx():
    for seed in range(150):
        rnd = random.Random(seed)
        n = rnd.randint(4, 45)
        directed = seed % 2 == 0
        multi = seed % 4 == 0
        G = nx.gnp_random_graph(n, rnd.uniform(0.08, 0.4), seed=seed, directed=directed)
        if multi:
            G = nx.MultiDiGraph(G) if directed else nx.MultiGraph(G)
            for _ in range(5):
                G.add_edge(rnd.randrange(n), rnd.randrange(n))
        if seed % 5 == 0 and n > 2:
            G.add_edge(0, 0)  # self-loop -> fallback
        for nd in G.nodes():
            G.nodes[nd]["v"] = rnd.uniform(0, 10)
            G.nodes[nd]["cat"] = rnd.choice("xyzw")
        Gf = _cp(G, directed, multi)
        if G.number_of_edges() == 0:
            continue
        assert _close(
            nx.numeric_assortativity_coefficient(G, "v"),
            fnx.numeric_assortativity_coefficient(Gf, "v"),
        ), seed
        assert _close(
            nx.attribute_assortativity_coefficient(G, "cat"),
            fnx.attribute_assortativity_coefficient(Gf, "cat"),
        ), seed


def test_nx_typed_input_falls_back():
    G = nx.gnp_random_graph(30, 0.2, seed=1)
    for nd in G.nodes():
        G.nodes[nd]["v"] = nd % 4
    assert _close(
        nx.numeric_assortativity_coefficient(G, "v"),
        fnx.numeric_assortativity_coefficient(G, "v"),
    )


def test_nodes_subset_falls_back():
    G = nx.gnp_random_graph(40, 0.2, seed=3)
    for nd in G.nodes():
        G.nodes[nd]["v"] = nd % 5
    Gf = _cp(G)
    sub = list(range(15))
    assert _close(
        nx.numeric_assortativity_coefficient(G, "v", nodes=sub),
        fnx.numeric_assortativity_coefficient(Gf, "v", nodes=sub),
    )


def test_missing_attribute_raises_keyerror():
    Gf = _cp(nx.path_graph(5))
    try:
        fnx.numeric_assortativity_coefficient(Gf, "absent")
    except KeyError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected KeyError for missing attribute")


def test_perfect_assortativity_clean_values():
    # A path with alternating categories has known assortativity; the fast path
    # must reproduce networkx's exact value.
    G = nx.path_graph(8)
    for nd in G.nodes():
        G.nodes[nd]["cat"] = nd % 2
    Gf = _cp(G)
    assert _close(
        nx.attribute_assortativity_coefficient(G, "cat"),
        fnx.attribute_assortativity_coefficient(Gf, "cat"),
    )
