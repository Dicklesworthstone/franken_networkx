"""Parity for ``triadic_census`` dict iteration order.

Bead br-r37-c1-v9m7b. fnx returned the 16 triad-type keys in arbitrary
Rust internal order (e.g. ['120U', '300', '012', '111D', ...]). nx
returns them in the canonical MAN-notation order
['003', '012', '102', '021D', '021U', '021C', '111D', '111U', '030T',
'030C', '201', '120D', '120U', '120C', '210', '300']. Drop-in code
that iterates the dict (or serialises it to JSON/CSV expecting
canonical order) broke.
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


CANONICAL_ORDER = [
    "003", "012", "102", "021D", "021U", "021C",
    "111D", "111U", "030T", "030C", "201",
    "120D", "120U", "120C", "210", "300",
]


@needs_nx
def test_triadic_census_keys_in_canonical_order():
    G = fnx.DiGraph([(0, 1), (1, 2), (2, 0)])
    f = fnx.triadic_census(G)
    assert list(f.keys()) == CANONICAL_ORDER


@needs_nx
def test_triadic_census_keys_match_networkx():
    G = fnx.DiGraph([(0, 1), (1, 2), (2, 0)])
    GX = nx.DiGraph([(0, 1), (1, 2), (2, 0)])
    f = fnx.triadic_census(G)
    n = nx.triadic_census(GX)
    assert list(f.keys()) == list(n.keys())


@needs_nx
def test_triadic_census_values_unchanged():
    """Reordering must not change values."""
    G = fnx.DiGraph([(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 2)])
    GX = nx.DiGraph([(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 2)])
    f = fnx.triadic_census(G)
    n = nx.triadic_census(GX)
    assert dict(f) == dict(n)


@needs_nx
def test_triadic_census_all_16_types_present():
    """Even on tiny graphs, all 16 triad types must appear (with 0 counts)."""
    G = fnx.DiGraph([(0, 1)])
    f = fnx.triadic_census(G)
    assert len(f) == 16
    assert all(t in f for t in CANONICAL_ORDER)


@needs_nx
def test_triadic_census_with_nodelist_kwarg():
    """nodelist-filtered form delegates to nx — order should still be
    canonical because nx itself returns canonical."""
    G = fnx.DiGraph([(0, 1), (1, 2), (2, 0), (2, 3)])
    GX = nx.DiGraph([(0, 1), (1, 2), (2, 0), (2, 3)])
    f = fnx.triadic_census(G, nodelist=[0, 1])
    n = nx.triadic_census(GX, nodelist=[0, 1])
    assert list(f.keys()) == list(n.keys())


@needs_nx
def test_undirected_input_raises_networkxerror():
    """Regression: the directed-only guard must not regress."""
    G = fnx.path_graph(3)
    with pytest.raises(fnx.NetworkXError):
        fnx.triadic_census(G)
