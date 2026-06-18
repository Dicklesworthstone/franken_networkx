"""Differential + bijection parity for Prüfer sequence encode/decode.

``to_prufer_sequence(T)`` maps a labeled tree on nodes ``0..n-1`` to its
length ``n-2`` Prüfer sequence; ``from_prufer_sequence(seq)`` is the
inverse. Neither had a dedicated test file.

This locks fnx against the real upstream networkx with:

* differential parity for both directions on random labeled trees and
  random sequences,
* the bijection round-trips (``to ∘ from`` and ``from ∘ to`` are
  identities),
* metamorphic invariants independent of the reference — node ``v``
  appears exactly ``deg(v) - 1`` times in the sequence, and the sequence
  length is ``n - 2``,
* hand-computed goldens (star → all-center, path → interior chain), and
* error contracts: non-tree input raises ``NotATree`` and a tree whose
  nodes are not ``0..n-1`` raises ``KeyError`` — in both libraries.

br-r37-c1-srrd2
"""

from __future__ import annotations

import random
from collections import Counter

import pytest
import networkx as nx

import franken_networkx as fnx


def _random_labeled_tree_pair(seed):
    """Build the same random tree on nodes 0..n-1 in fnx and nx."""
    rng = random.Random(seed)
    n = rng.randint(3, 13)
    nodes = list(range(n))
    rng.shuffle(nodes)
    ftree = fnx.Graph()
    ntree = nx.Graph()
    ftree.add_node(nodes[0])
    ntree.add_node(nodes[0])
    for i in range(1, n):
        parent = nodes[rng.randint(0, i - 1)]
        ftree.add_edge(nodes[i], parent)
        ntree.add_edge(nodes[i], parent)
    return ftree, ntree, n


def _edge_set(G):
    return sorted(tuple(sorted(e)) for e in G.edges())


# ---------------------------------------------------------------------------
# Differential parity, both directions.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(60))
def test_to_prufer_sequence_matches_networkx(seed):
    ftree, ntree, n = _random_labeled_tree_pair(seed)
    fs = fnx.to_prufer_sequence(ftree)
    ns = nx.to_prufer_sequence(ntree)
    assert fs == ns, f"seed={seed}: fnx={fs} nx={ns}"
    assert len(fs) == n - 2


@pytest.mark.parametrize("seed", range(60))
def test_from_prufer_sequence_matches_networkx(seed):
    rng = random.Random(seed * 31 + 7)
    k = rng.randint(1, 11)
    n = k + 2
    seq = [rng.randint(0, n - 1) for _ in range(k)]
    ftree = fnx.from_prufer_sequence(list(seq))
    ntree = nx.from_prufer_sequence(list(seq))
    assert _edge_set(ftree) == _edge_set(ntree), f"seed={seed} seq={seq}"
    assert sorted(map(int, ftree.nodes())) == list(range(n))


# ---------------------------------------------------------------------------
# Bijection round-trips.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(60))
def test_tree_roundtrips_through_prufer(seed):
    ftree, _, _ = _random_labeled_tree_pair(seed)
    recovered = fnx.from_prufer_sequence(fnx.to_prufer_sequence(ftree))
    assert _edge_set(recovered) == _edge_set(ftree)


@pytest.mark.parametrize("seed", range(60))
def test_sequence_roundtrips_through_tree(seed):
    rng = random.Random(seed * 17 + 3)
    k = rng.randint(1, 11)
    n = k + 2
    seq = [rng.randint(0, n - 1) for _ in range(k)]
    back = fnx.to_prufer_sequence(fnx.from_prufer_sequence(list(seq)))
    assert back == seq


# ---------------------------------------------------------------------------
# Metamorphic invariant: node v appears deg(v) - 1 times.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(40))
def test_prufer_degree_invariant(seed):
    ftree, _, n = _random_labeled_tree_pair(seed)
    seq = fnx.to_prufer_sequence(ftree)
    counts = Counter(seq)
    for v in range(n):
        assert counts.get(v, 0) == ftree.degree(v) - 1, f"seed={seed} node={v}"


# ---------------------------------------------------------------------------
# Hand-computed goldens.
# ---------------------------------------------------------------------------


def test_star_graph_golden():
    # star_graph(4): center 0 with leaves 1..4 → Prüfer is [0, 0, 0].
    assert fnx.to_prufer_sequence(fnx.star_graph(4)) == [0, 0, 0]
    assert _edge_set(fnx.from_prufer_sequence([0, 0, 0])) == [
        (0, 1), (0, 2), (0, 3), (0, 4)
    ]


def test_path_graph_golden():
    # path 0-1-2-3-4 → Prüfer is the interior chain [1, 2, 3].
    assert fnx.to_prufer_sequence(fnx.path_graph(5)) == [1, 2, 3]
    assert _edge_set(fnx.from_prufer_sequence([1, 2, 3])) == [
        (0, 1), (1, 2), (2, 3), (3, 4)
    ]


# ---------------------------------------------------------------------------
# Error contracts.
# ---------------------------------------------------------------------------


def test_to_prufer_rejects_non_tree_like_networkx():
    fg = fnx.Graph([(0, 1), (1, 2), (2, 0)])
    ng = nx.Graph([(0, 1), (1, 2), (2, 0)])
    with pytest.raises(nx.NotATree):
        fnx.to_prufer_sequence(fg)
    with pytest.raises(nx.NotATree):
        nx.to_prufer_sequence(ng)


def test_to_prufer_rejects_non_contiguous_labels_like_networkx():
    fg = fnx.Graph([(1, 2), (2, 3)])
    ng = nx.Graph([(1, 2), (2, 3)])
    with pytest.raises(KeyError):
        fnx.to_prufer_sequence(fg)
    with pytest.raises(KeyError):
        nx.to_prufer_sequence(ng)
