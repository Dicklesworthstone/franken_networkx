"""Parity for ``center`` / ``periphery`` node iteration order.

Bead br-r37-c1-6qcaw. fnx.center and fnx.periphery used the Rust
_raw_* implementations which returned nodes in canonical / Rust-
internal order rather than nx's node-insertion order.

Eccentricity values matched between libs; only the periphery's /
center's iteration order differed. nx's contract is to iterate
the eccentricity dict (which has node-insertion-order keys) and
emit nodes whose eccentricity equals the max (periphery) or
min (center).

Repro: balanced_tree(2, 3)
  fnx.periphery -> [10, 11, 12, 13, 14, 7, 8, 9]
  nx.periphery  -> [7, 8, 9, 10, 11, 12, 13, 14]
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


@needs_nx
def test_balanced_tree_periphery_order_matches_nx():
    """The repro case from the bead."""
    t = fnx.balanced_tree(2, 3)
    tx = nx.balanced_tree(2, 3)
    assert fnx.periphery(t) == nx.periphery(tx)


@needs_nx
def test_balanced_tree_center_matches_nx():
    t = fnx.balanced_tree(2, 3)
    tx = nx.balanced_tree(2, 3)
    assert fnx.center(t) == nx.center(tx)


@needs_nx
def test_path_graph_periphery_matches_nx():
    g = fnx.path_graph(5)
    gx = nx.path_graph(5)
    assert fnx.periphery(g) == nx.periphery(gx)


@needs_nx
def test_path_graph_center_matches_nx():
    g = fnx.path_graph(5)
    gx = nx.path_graph(5)
    assert fnx.center(g) == nx.center(gx)


@needs_nx
def test_cycle_graph_all_in_periphery_matches_nx():
    """Cycle: every node has same eccentricity, so all in periphery."""
    g = fnx.cycle_graph(6)
    gx = nx.cycle_graph(6)
    assert fnx.periphery(g) == nx.periphery(gx)
    assert fnx.center(g) == nx.center(gx)


@needs_nx
def test_complete_graph_periphery_matches_nx():
    """K_n: all nodes have eccentricity 1."""
    g = fnx.complete_graph(5)
    gx = nx.complete_graph(5)
    assert fnx.periphery(g) == nx.periphery(gx)
    assert fnx.center(g) == nx.center(gx)


@needs_nx
def test_str_node_path_matches_nx():
    edges = [("a", "b"), ("b", "c"), ("c", "d"), ("d", "e")]
    g = fnx.Graph()
    gx = nx.Graph()
    for u, v in edges:
        g.add_edge(u, v)
        gx.add_edge(u, v)
    assert fnx.periphery(g) == nx.periphery(gx)
    assert fnx.center(g) == nx.center(gx)


@needs_nx
def test_specific_periphery_order_regression():
    """Regression: nx returns [7,8,9,10,11,12,13,14] in that order
    for balanced_tree(2,3) — fnx must emit the same order."""
    t = fnx.balanced_tree(2, 3)
    assert fnx.periphery(t) == [7, 8, 9, 10, 11, 12, 13, 14]


@needs_nx
def test_periphery_with_e_kwarg_delegates_and_matches_nx():
    """e= kwarg path delegates to nx — sanity check."""
    g = fnx.path_graph(5)
    gx = nx.path_graph(5)
    e = fnx.eccentricity(g)
    e_nx = nx.eccentricity(gx)
    assert fnx.periphery(g, e=e) == nx.periphery(gx, e=e_nx)


@needs_nx
def test_center_with_e_kwarg_delegates_and_matches_nx():
    g = fnx.path_graph(5)
    gx = nx.path_graph(5)
    e = fnx.eccentricity(g)
    e_nx = nx.eccentricity(gx)
    assert fnx.center(g, e=e) == nx.center(gx, e=e_nx)


@needs_nx
def test_empty_graph_raises_matching_nx():
    """nx raises ValueError on periphery (max() of empty) and
    NetworkXPointlessConcept on center (is_tree check first)."""
    g = fnx.Graph()
    with pytest.raises(ValueError):
        fnx.periphery(g)
    with pytest.raises(fnx.NetworkXPointlessConcept):
        fnx.center(g)


@needs_nx
def test_grid_graph_periphery_matches_nx():
    """grid_graph has tuple nodes — verify those work too."""
    g = fnx.grid_graph([3, 3])
    gx = nx.grid_graph([3, 3])
    assert fnx.periphery(g) == nx.periphery(gx)
    assert fnx.center(g) == nx.center(gx)
