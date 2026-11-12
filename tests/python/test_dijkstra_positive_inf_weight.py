"""br-r37-c1-z35td: regression — fnx.dijkstra family must not silently
substitute ``float('inf')`` edge weights with the unit default.

Pre-fix, the Rust ``edge_weight_or_default`` helper filtered out
non-finite values via ``.filter(|v| v.is_finite() && *v >= 0.0)`` and
fell back to ``1.0``, so an ``inf``-weighted edge was traversed as if
unit-weighted. The fnx dijkstra wrapper now delegates any graph
containing a ``+inf`` weight to nx (mirroring the existing ``-inf`` and
negative-weight delegation path), which correctly treats ``inf`` as
"edge exists but is never relaxed" and routes around it via any finite
alternative.
"""

from __future__ import annotations

import math

import pytest

import franken_networkx as fnx

try:
    import networkx as nx

    HAS_NX = True
except ImportError:
    HAS_NX = False


needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


def _make_inf_alt_graph(cls):
    g = cls()
    g.add_edge(0, 1, weight=float("inf"))
    g.add_edge(0, 2, weight=1.0)
    g.add_edge(2, 1, weight=1.0)
    return g


@needs_nx
def test_dijkstra_path_avoids_inf_weighted_edge():
    fg = _make_inf_alt_graph(fnx.Graph)
    ng = _make_inf_alt_graph(nx.Graph)
    assert fnx.dijkstra_path(fg, 0, 1, weight="weight") == nx.dijkstra_path(ng, 0, 1, weight="weight")
    assert fnx.dijkstra_path(fg, 0, 1, weight="weight") == [0, 2, 1]


@needs_nx
def test_dijkstra_path_length_skips_inf_edge():
    fg = _make_inf_alt_graph(fnx.Graph)
    ng = _make_inf_alt_graph(nx.Graph)
    fl = fnx.dijkstra_path_length(fg, 0, 1, weight="weight")
    nl = nx.dijkstra_path_length(ng, 0, 1, weight="weight")
    assert fl == nl
    assert fl == 2.0
    assert not math.isinf(fl)


@needs_nx
def test_single_source_dijkstra_path_skips_inf_edge():
    fg = _make_inf_alt_graph(fnx.Graph)
    ng = _make_inf_alt_graph(nx.Graph)
    fp = fnx.single_source_dijkstra_path(fg, 0, weight="weight")
    np = nx.single_source_dijkstra_path(ng, 0, weight="weight")
    assert dict(fp) == dict(np)
    assert fp[1] == [0, 2, 1]


@needs_nx
def test_single_source_dijkstra_path_length_skips_inf_edge():
    fg = _make_inf_alt_graph(fnx.Graph)
    ng = _make_inf_alt_graph(nx.Graph)
    fl = fnx.single_source_dijkstra_path_length(fg, 0, weight="weight")
    nl = nx.single_source_dijkstra_path_length(ng, 0, weight="weight")
    assert dict(fl) == dict(nl)
    assert fl[1] == 2.0


@needs_nx
def test_dijkstra_inf_only_path_raises_no_path_like_nx():
    """If the *only* path to a target uses an inf-weighted edge, nx
    treats it as unreachable. fnx should too (after the fix)."""
    fg = fnx.Graph()
    fg.add_edge(0, 1, weight=float("inf"))
    fg.add_edge(2, 3, weight=1.0)
    ng = nx.Graph()
    ng.add_edge(0, 1, weight=float("inf"))
    ng.add_edge(2, 3, weight=1.0)
    # nx with all-inf path returns length=inf without raising
    fl = fnx.dijkstra_path_length(fg, 0, 1, weight="weight")
    nl = nx.dijkstra_path_length(ng, 0, 1, weight="weight")
    assert fl == nl
    # Both should treat 0→1 as unreachable (no finite alternative)
    # — actual return depends on nx's handling; we just match.


@needs_nx
def test_dijkstra_finite_weights_no_regression():
    """Confirm the inf-delegation path doesn't break ordinary
    finite-weight graphs."""
    fg = fnx.Graph([(0, 1, {"weight": 1}), (1, 2, {"weight": 2}), (0, 2, {"weight": 5})])
    ng = nx.Graph([(0, 1, {"weight": 1}), (1, 2, {"weight": 2}), (0, 2, {"weight": 5})])
    assert fnx.dijkstra_path(fg, 0, 2, weight="weight") == nx.dijkstra_path(ng, 0, 2, weight="weight")


@needs_nx
def test_astar_path_avoids_inf_weighted_edge():
    """br-r37-c1-nncon: same +inf-as-1.0 bug as dijkstra, hit astar_path too."""
    fg = _make_inf_alt_graph(fnx.Graph)
    ng = _make_inf_alt_graph(nx.Graph)
    assert fnx.astar_path(fg, 0, 1, weight="weight") == nx.astar_path(ng, 0, 1, weight="weight")
    assert fnx.astar_path(fg, 0, 1, weight="weight") == [0, 2, 1]


@needs_nx
def test_astar_path_length_skips_inf_edge():
    fg = _make_inf_alt_graph(fnx.Graph)
    ng = _make_inf_alt_graph(nx.Graph)
    fl = fnx.astar_path_length(fg, 0, 1, weight="weight")
    nl = nx.astar_path_length(ng, 0, 1, weight="weight")
    assert fl == nl
    assert fl == 2.0


@needs_nx
def test_dijkstra_inf_in_directed_graph():
    fg = fnx.DiGraph()
    fg.add_edge(0, 1, weight=float("inf"))
    fg.add_edge(0, 2, weight=1.0)
    fg.add_edge(2, 1, weight=1.0)
    ng = nx.DiGraph()
    ng.add_edge(0, 1, weight=float("inf"))
    ng.add_edge(0, 2, weight=1.0)
    ng.add_edge(2, 1, weight=1.0)
    assert fnx.dijkstra_path(fg, 0, 1, weight="weight") == nx.dijkstra_path(ng, 0, 1, weight="weight")
    assert fnx.dijkstra_path(fg, 0, 1, weight="weight") == [0, 2, 1]
