"""Metamorphic codec round-trip relations (encode then decode == identity).

* Prüfer: ``to_prufer_sequence(from_prufer_sequence(seq)) == seq``
* graph6 / sparse6: ``from_*(to_*(G))`` recovers the graph, and the bytes
  match networkx
* nested tuple: ``from_nested_tuple(to_nested_tuple(tree, root))`` is
  isomorphic to the original tree

NOTE: graph6/sparse6 encode the adjacency matrix in node-iteration order,
so a graph built off an edge list (non-canonical node order) round-trips to
a relabelled graph. These tests use canonical node order (0..n-1 added
first), which is the meaningful round-trip contract.

br-r37-c1-6ljry
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _canonical_graph(seed, n=6, p=0.4):
    g = nx.gnp_random_graph(n, p, seed=seed)
    fg = fnx.Graph()
    fg.add_nodes_from(range(n))      # canonical order first
    for u, v in g.edges():
        fg.add_edge(u, v)
    return fg, g


def _edge_set(g):
    return sorted(tuple(sorted(e)) for e in g.edges())


@pytest.mark.parametrize("seed", range(50))
def test_prufer_round_trip(seed):
    rng = random.Random(seed)
    n = rng.randint(3, 9)
    seq = [rng.randint(0, n - 1) for _ in range(n - 2)]
    tree = fnx.from_prufer_sequence(seq)
    assert list(fnx.to_prufer_sequence(tree)) == seq


@pytest.mark.parametrize("seed", range(50))
def test_graph6_round_trip_and_parity(seed):
    fg, g = _canonical_graph(seed)
    encoded = fnx.to_graph6_bytes(fg, header=False)
    assert encoded == nx.to_graph6_bytes(g, header=False)
    assert _edge_set(fnx.from_graph6_bytes(encoded.strip())) == _edge_set(fg)


@pytest.mark.parametrize("seed", range(50))
def test_sparse6_round_trip(seed):
    fg, _ = _canonical_graph(seed)
    encoded = fnx.to_sparse6_bytes(fg, header=False)
    decoded = fnx.from_sparse6_bytes(encoded.strip())
    assert _edge_set(decoded) == _edge_set(fg)


@pytest.mark.parametrize("seed", range(30))
def test_nested_tuple_round_trip(seed):
    rng = random.Random(seed)
    n = rng.randint(3, 7)
    seq = [rng.randint(0, n - 1) for _ in range(n - 2)]
    tree = fnx.from_prufer_sequence(seq)
    nested = fnx.to_nested_tuple(tree, 0)
    rebuilt = fnx.from_nested_tuple(nested)
    assert nx.is_isomorphic(
        nx.Graph(list(tree.edges())), nx.Graph(list(rebuilt.edges()))
    )
