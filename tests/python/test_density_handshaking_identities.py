"""Density + handshaking identities (density/degree/edges cross-checks).

Basic but foundational counting identities, cross-checking density and the
degree views against the edge count:
  - undirected density(G) = 2|E| / (n(n-1));  directed = |E| / (n(n-1));
  - density(K_n) = 1, density(empty) = 0;
  - handshaking lemma: sum of degrees = 2|E| (undirected);
  - directed: sum(in_degree) = sum(out_degree) = |E|.
Oracle-free, independent of networkx.

These identities are exact equalities, so the assertions are already strong; what
they were missing is REACH. The random families here are simple graphs with
n >= 3, which leaves out every case where the counting is interesting: a
self-loop (which contributes 2 to an undirected degree, and one in plus one out
when directed), parallel edges, and the n <= 1 boundary where the n(n-1)
denominator would divide by zero. Those are covered below, on Graph, DiGraph,
MultiGraph and MultiDiGraph.

No mocks: real fnx.
"""

from __future__ import annotations

import random

import pytest
import franken_networkx as fnx


@pytest.mark.parametrize("n", [3, 4, 5, 6, 7])
def test_density_closed_forms(n):
    assert fnx.density(fnx.complete_graph(n)) == pytest.approx(1.0)
    e = fnx.empty_graph(n)
    assert fnx.density(e) == pytest.approx(0.0)


@pytest.mark.parametrize("seed", range(30))
def test_undirected_density_and_handshaking(seed):
    r = random.Random(seed)
    n = r.randint(3, 9)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.5]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)
    E = g.number_of_edges()
    assert fnx.density(g) == pytest.approx(2 * E / (n * (n - 1)))
    # Handshaking lemma.
    assert sum(d for _, d in g.degree()) == 2 * E


@pytest.mark.parametrize("seed", range(30))
def test_directed_density_and_degree_sums(seed):
    r = random.Random(seed)
    n = r.randint(3, 9)
    arcs = [(u, v) for u in range(n) for v in range(n) if u != v and r.random() < 0.35]
    d = fnx.DiGraph(); d.add_nodes_from(range(n)); d.add_edges_from(arcs)
    E = d.number_of_edges()
    assert fnx.density(d) == pytest.approx(E / (n * (n - 1)))
    # Every arc contributes one in-degree and one out-degree.
    assert sum(x for _, x in d.in_degree()) == E
    assert sum(x for _, x in d.out_degree()) == E
    # A DiGraph's degree is the sum of the two directed degrees, per node.
    assert all(d.in_degree(v) + d.out_degree(v) == d.degree(v) for v in d.nodes())


@pytest.mark.parametrize("n", [0, 1])
def test_density_is_zero_at_the_degenerate_boundary(n):
    """n(n-1) is 0 here, so density is defined to be 0 rather than dividing by it.

    The random families start at n = 3 and never reach this.
    """
    assert fnx.density(fnx.empty_graph(n)) == 0
    assert fnx.density(fnx.DiGraph()) == 0


def test_self_loops_count_twice_undirected_and_once_each_way_directed():
    g = fnx.Graph(); g.add_edges_from([(0, 1), (1, 2)]); g.add_edge(0, 0)
    # The loop adds 2 to node 0's degree, so handshaking still gives 2|E|.
    assert g.degree(0) == 3
    assert sum(d for _, d in g.degree()) == 2 * g.number_of_edges()

    d = fnx.DiGraph(); d.add_edge(0, 0); d.add_edge(0, 1)
    assert (d.in_degree(0), d.out_degree(0), d.degree(0)) == (1, 2, 3)
    E = d.number_of_edges()
    assert sum(x for _, x in d.in_degree()) == sum(x for _, x in d.out_degree()) == E


@pytest.mark.parametrize("seed", range(30))
def test_multigraph_identities_count_multiplicity(seed):
    """Parallel edges and loops each count once toward |E| and twice toward degree."""
    r = random.Random(seed)
    n = r.randint(3, 9)
    m = fnx.MultiGraph(); m.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u, n):          # v == u included, so self-loops occur
            for _ in range(r.randint(0, 2)):
                m.add_edge(u, v)

    E = m.number_of_edges()
    assert sum(d for _, d in m.degree()) == 2 * E
    assert fnx.density(m) == pytest.approx(2 * E / (n * (n - 1)))


@pytest.mark.parametrize("seed", range(30))
def test_multidigraph_identities_count_multiplicity(seed):
    r = random.Random(seed)
    n = r.randint(3, 9)
    d = fnx.MultiDiGraph(); d.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            for _ in range(r.randint(0, 1)):
                d.add_edge(u, v)

    E = d.number_of_edges()
    assert sum(x for _, x in d.in_degree()) == E
    assert sum(x for _, x in d.out_degree()) == E
    assert fnx.density(d) == pytest.approx(E / (n * (n - 1)))


@pytest.mark.parametrize("seed", range(30))
def test_degree_view_forms_all_agree(seed):
    """The bead cross-checks degree VIEWS: iteration, dict(), and per-node calls."""
    r = random.Random(seed)
    n = r.randint(3, 9)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.5]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)

    by_iteration = sum(d for _, d in g.degree())
    by_dict = sum(dict(g.degree()).values())
    by_node = sum(g.degree(v) for v in g.nodes())
    assert by_iteration == by_dict == by_node == 2 * g.number_of_edges()
    assert dict(g.degree()) == {v: g.degree(v) for v in g.nodes()}
