"""Coloring + approximation: validity invariants + networkx parity.

A graph coloring is *proper* iff no edge is monochromatic; a vertex cover must
touch every edge; an independent set must contain no edge; a dominating set
must dominate every node. These validity invariants hold regardless of any
reference implementation. greedy_color's deterministic strategies additionally
match networkx exactly.

No mocks: real fnx and real networkx on random graphs.
"""

from __future__ import annotations

import itertools
import random

import pytest
import networkx as nx
import franken_networkx as fnx

_STRATEGIES = [
    "largest_first", "smallest_last", "independent_set", "DSATUR",
    "connected_sequential_bfs", "connected_sequential_dfs",
    "saturation_largest_first",
]


def _graph(seed):
    r = random.Random(seed)
    n = r.randint(6, 12)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.4]
    fg = fnx.Graph(); fg.add_nodes_from(range(n)); fg.add_edges_from(edges)
    ng = nx.Graph(); ng.add_nodes_from(range(n)); ng.add_edges_from(edges)
    return fg, ng, n, edges


@pytest.mark.parametrize("strategy", _STRATEGIES)
@pytest.mark.parametrize("seed", range(20))
def test_greedy_color_parity_and_validity(strategy, seed):
    fg, ng, n, edges = _graph(seed)
    coloring = fnx.greedy_color(fg, strategy=strategy)
    assert coloring == nx.greedy_color(ng, strategy=strategy)
    # Proper coloring: no edge is monochromatic.
    assert all(coloring[u] != coloring[v] for u, v in edges)


@pytest.mark.parametrize("seed", range(40))
def test_approximation_outputs_are_valid(seed):
    fg, ng, n, edges = _graph(seed)
    adj = {i: set() for i in range(n)}
    for u, v in edges:
        adj[u].add(v)
        adj[v].add(u)

    # Vertex cover touches every edge.
    vc = fnx.approximation.min_weighted_vertex_cover(fg)
    assert all(u in vc or v in vc for u, v in edges)

    # Independent set contains no edge.
    mis = fnx.approximation.maximum_independent_set(fg)
    assert all(not (u in mis and v in mis) for u, v in edges)

    # Dominating set dominates every node.
    ds = fnx.approximation.min_weighted_dominating_set(fg)
    assert all(node in ds or (adj[node] & ds) for node in range(n))


@pytest.mark.parametrize("seed", range(40))
def test_approximation_outputs_are_nonempty_subsets(seed):
    """"Contains no edge" is satisfied by the EMPTY set.

    maximum_independent_set is validated only by the absence of an internal
    edge, so a function returning nothing passes. The cover and dominating set
    are constrained from below by their own checks, but none of the three was
    required to consist of the graph's own nodes.
    """
    fg, _, n, edges = _graph(seed)
    nodes = set(fg.nodes())

    cover = set(fnx.approximation.min_weighted_vertex_cover(fg))
    independent = set(fnx.approximation.maximum_independent_set(fg))
    dominating = set(fnx.approximation.min_weighted_dominating_set(fg))

    for result in (cover, independent, dominating):
        assert result <= nodes

    # A graph with nodes always has a non-empty independent set: any single
    # node is one. An empty return would satisfy the no-internal-edge check.
    assert independent


@pytest.mark.parametrize("seed", range(40))
def test_vertex_cover_complement_is_independent(seed):
    """Cross-check between two of the three outputs, independent of both.

    The complement of a vertex cover is an independent set by definition, so
    this ties the cover to the same property the independent set is judged by.
    """
    fg, _, n, edges = _graph(seed)
    cover = set(fnx.approximation.min_weighted_vertex_cover(fg))
    complement = set(fg.nodes()) - cover
    for u, v in edges:
        assert not (u in complement and v in complement)


def _brute_force_min_weight_cover(edges, weights):
    """Exhaustive optimum — the approximation guarantee needs a real optimum."""
    nodes = sorted(weights)
    best = None
    for size in range(1, len(nodes) + 1):
        for combo in itertools.combinations(nodes, size):
            chosen = set(combo)
            if all(u in chosen or v in chosen for u, v in edges):
                total = sum(weights[v] for v in chosen)
                if best is None or total < best:
                    best = total
    return best


@pytest.mark.parametrize(
    "builder_name",
    ["add_node", "node_view", "set_node_attributes"],
)
def test_weighted_vertex_cover_respects_node_weights(builder_name):
    """Regression for br-r37-c1-bdswh.

    Node weights written AFTER construction never reached the store the native
    kernel read, so every cost fell back to 1 and the weighted call silently
    returned the UNWEIGHTED cover. All three ways of attaching the weights must
    give the same answer, and it must respect the 2-approximation guarantee —
    parity with networkx alone would not catch a future regression that was
    wrong in the same direction.
    """
    edges = [(0, 1), (1, 2), (2, 3), (3, 0), (0, 2)]
    weights = {0: 1, 1: 100, 2: 1, 3: 100}

    fg = fnx.Graph()
    if builder_name == "add_node":
        for node, w in weights.items():
            fg.add_node(node, weight=w)
        fg.add_edges_from(edges)
    else:
        fg.add_edges_from(edges)
        if builder_name == "node_view":
            for node, w in weights.items():
                fg.nodes[node]["weight"] = w
        else:
            fnx.set_node_attributes(fg, weights, "weight")

    cover = set(fnx.approximation.min_weighted_vertex_cover(fg, weight="weight"))
    assert all(u in cover or v in cover for u, v in edges)      # still a cover

    total = sum(weights[v] for v in cover)
    optimum = _brute_force_min_weight_cover(edges, weights)
    assert total <= 2 * optimum                                  # the guarantee

    ng = nx.Graph()
    ng.add_edges_from(edges)
    nx.set_node_attributes(ng, weights, "weight")
    assert cover == set(nx.approximation.min_weighted_vertex_cover(ng, weight="weight"))
