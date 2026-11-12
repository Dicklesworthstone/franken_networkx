"""Differential + golden parity for ``prefix_tree``.

``prefix_tree(paths)`` builds a trie: a rooted tree whose root is node 0,
with a ``nil`` sentinel leaf, where each node carries a ``source``
attribute. No dedicated test file existed.

br-r37-c1-m1qhy
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _signature(G):
    return (
        sorted((str(n), str(d.get("source"))) for n, d in G.nodes(data=True)),
        sorted((str(u), str(v)) for u, v in G.edges()),
    )


@pytest.mark.parametrize("seed", range(60))
def test_prefix_tree_matches_networkx(seed):
    rng = random.Random(seed)
    paths = [
        "".join(rng.choice("abc") for _ in range(rng.randint(1, 4)))
        for _ in range(rng.randint(1, 5))
    ]
    assert _signature(fnx.prefix_tree(paths)) == _signature(nx.prefix_tree(paths))


def test_prefix_tree_golden():
    paths = ["ab", "abc", "b"]
    ft = fnx.prefix_tree(paths)
    nt = nx.prefix_tree(paths)
    assert ft.number_of_nodes() == nt.number_of_nodes()
    assert _signature(ft) == _signature(nt)
    # Root is node 0.
    assert 0 in ft


def test_prefix_tree_empty_matches_networkx():
    # Just the root and the nil sentinel.
    assert _signature(fnx.prefix_tree([])) == _signature(nx.prefix_tree([]))
    assert fnx.prefix_tree([]).number_of_nodes() == nx.prefix_tree([]).number_of_nodes()
