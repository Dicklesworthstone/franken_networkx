"""Gallai's identity: matching number + edge cover number = n.

For a graph with no isolated vertices, Gallai's theorem states
  nu(G) + rho(G) = |V|,
where nu is the maximum matching size and rho is the minimum edge cover size.
This cross-checks two independent algorithms (max_weight_matching and
min_edge_cover) against each other AND the node count — a strong oracle-free
invariant. Cardinality parity with networkx and edge-cover validity are also
checked.

No mocks: real fnx and real networkx.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _no_isolates_graph(seed):
    r = random.Random(seed)
    n = r.randint(4, 8)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.5]
    fg = fnx.Graph(); fg.add_nodes_from(range(n)); fg.add_edges_from(edges)
    ng = nx.Graph(); ng.add_nodes_from(range(n)); ng.add_edges_from(edges)
    return fg, ng, n


@pytest.mark.parametrize("seed", range(40))
def test_gallai_matching_plus_edge_cover_equals_n(seed):
    fg, ng, n = _no_isolates_graph(seed)
    if any(d == 0 for _, d in fg.degree()):
        pytest.skip("has isolated vertex (identity needs none)")

    nu = len(fnx.max_weight_matching(fg))    # maximum matching cardinality
    rho = len(fnx.min_edge_cover(fg))         # minimum edge cover cardinality
    # Gallai: nu + rho == n.
    assert nu + rho == n
    # Both cardinalities match networkx.
    assert len(nx.max_weight_matching(ng)) == nu
    assert len(nx.min_edge_cover(ng)) == rho


@pytest.mark.parametrize("seed", range(40))
def test_min_edge_cover_is_valid(seed):
    fg, ng, n = _no_isolates_graph(seed)
    if any(d == 0 for _, d in fg.degree()):
        pytest.skip("has isolated vertex")
    ec = fnx.min_edge_cover(fg)
    covered = set()
    for u, v in ec:
        covered.add(u)
        covered.add(v)
    # An edge cover must touch every node.
    assert covered == set(range(n))


def test_matching_is_valid_on_named_graphs():
    # A perfect matching on an even cycle covers all nodes in n/2 disjoint edges.
    g = fnx.cycle_graph(6)
    m = fnx.max_weight_matching(g)
    assert len(m) == 3
    seen = set()
    for u, v in m:
        assert u not in seen and v not in seen  # disjoint (a real matching)
        seen.add(u); seen.add(v)


@pytest.mark.parametrize("seed", range(40))
def test_cover_and_matching_are_made_of_graph_edges(seed):
    """Cardinalities and coverage say nothing about where the edges came from.

    The sweep above compares only sizes, and disjointness is asserted on
    cycle_graph(6) alone — so on the random family a matching of non-adjacent
    pairs, or a cover using edges absent from G, satisfies everything.
    """
    fg, _, n = _no_isolates_graph(seed)
    if any(d == 0 for _, d in fg.degree()):
        pytest.skip("has isolated vertex")

    cover = [tuple(e) for e in fnx.min_edge_cover(fg)]
    matching = [tuple(e) for e in fnx.max_weight_matching(fg)]

    for u, v in cover:
        assert fg.has_edge(u, v)
    for u, v in matching:
        assert fg.has_edge(u, v)

    # Disjointness, on every draw rather than one named graph.
    seen = set()
    for u, v in matching:
        assert u not in seen and v not in seen
        seen.add(u); seen.add(v)

    # A MINIMUM cover is in particular irredundant: drop any edge and some node
    # stops being covered.
    for i in range(len(cover)):
        remaining = cover[:i] + cover[i + 1:]
        still_covered = {x for edge in remaining for x in edge}
        assert still_covered != set(fg.nodes())


def test_isolated_vertex_is_refused_like_networkx():
    """Both sweeps SKIP graphs with an isolated vertex; this is what happens there.

    A node with no incident edge cannot be covered, so min_edge_cover raises
    rather than returning a partial cover — the contract the skip hides.
    """
    g = fnx.Graph([(0, 1)]); g.add_node(9)
    ng = nx.Graph([(0, 1)]); ng.add_node(9)

    def outcome(fn):
        try:
            return ("returned", sorted(map(tuple, fn())))
        except Exception as exc:  # noqa: BLE001 - the type IS the assertion
            return ("raised", type(exc).__name__)

    got = outcome(lambda: fnx.min_edge_cover(g))
    want = outcome(lambda: nx.min_edge_cover(ng))
    assert want[0] == "raised", "networkx no longer refuses this — retune the case"
    assert got == want
