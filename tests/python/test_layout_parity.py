"""Numeric parity for fnx.fruchterman_reingold_layout / spring_layout.

Bead: br-r37-c1-xditv. The implementation is a literal port of
networkx.drawing.layout._fruchterman_reingold and produces bit-stable
output for the same seed and adjacency matrix. The earlier divergence
report was an artefact of building the fnx graph via
``add_edges_from(GX.edges())`` — a 2-tuple form that drops edge data —
so the two graphs disagreed on edge weights. With weights preserved
(or weight=None) the two libraries agree to 1e-6.
"""

from __future__ import annotations

import numpy as np
import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


def _build_pair(builder):
    """Return matching (fnx_graph, nx_graph) — preserves edge data."""
    nx_graph = builder()
    f_graph = fnx.Graph()
    f_graph.add_nodes_from(nx_graph.nodes(data=True))
    f_graph.add_edges_from(nx_graph.edges(data=True))
    return f_graph, nx_graph


def _max_position_diff(p1: dict, p2: dict) -> float:
    return max(
        float(np.linalg.norm(np.asarray(p1[k]) - np.asarray(p2[k])))
        for k in p1
    )


@needs_nx
@pytest.mark.parametrize(
    ("name", "builder"),
    [
        ("path6", lambda: nx.path_graph(6)),
        ("complete5", lambda: nx.complete_graph(5)),
        ("karate", lambda: nx.karate_club_graph()),
        ("cycle8", lambda: nx.cycle_graph(8)),
    ],
)
def test_fruchterman_reingold_layout_matches_networkx(name, builder):
    f_graph, nx_graph = _build_pair(builder)
    fnx_pos = fnx.fruchterman_reingold_layout(f_graph, seed=42)
    nx_pos = nx.fruchterman_reingold_layout(nx_graph, seed=42)
    assert _max_position_diff(fnx_pos, nx_pos) < 1e-6


@needs_nx
@pytest.mark.parametrize(
    ("name", "builder"),
    [
        ("path6", lambda: nx.path_graph(6)),
        ("complete5", lambda: nx.complete_graph(5)),
        ("karate", lambda: nx.karate_club_graph()),
    ],
)
def test_spring_layout_matches_networkx(name, builder):
    f_graph, nx_graph = _build_pair(builder)
    fnx_pos = fnx.spring_layout(f_graph, seed=42)
    nx_pos = nx.spring_layout(nx_graph, seed=42)
    assert _max_position_diff(fnx_pos, nx_pos) < 1e-6


@needs_nx
def test_spring_layout_unweighted_matches_networkx_when_edges_lose_data():
    """The original bug report fed fnx.add_edges_from(GX.edges()) which drops
    weights; positions diverge in that setup *only because the adjacency
    matrices differ*. Calling with weight=None makes the result deterministic
    regardless of weight-attribute presence."""
    nx_graph = nx.karate_club_graph()
    f_graph = fnx.Graph()
    f_graph.add_nodes_from(nx_graph.nodes())
    f_graph.add_edges_from(nx_graph.edges())  # 2-tuple, no weights
    fnx_pos = fnx.fruchterman_reingold_layout(f_graph, seed=42, weight=None)
    nx_pos = nx.fruchterman_reingold_layout(nx_graph, seed=42, weight=None)
    assert _max_position_diff(fnx_pos, nx_pos) < 1e-6


@needs_nx
def test_fruchterman_reingold_with_initial_pos_matches_networkx():
    nx_graph = nx.path_graph(5)
    f_graph = fnx.path_graph(5)
    init_pos = {0: (0.0, 0.0), 4: (1.0, 0.0)}
    fnx_pos = fnx.fruchterman_reingold_layout(
        f_graph, pos=init_pos, fixed=[0, 4], seed=42
    )
    nx_pos = nx.fruchterman_reingold_layout(
        nx_graph, pos=init_pos, fixed=[0, 4], seed=42
    )
    assert _max_position_diff(fnx_pos, nx_pos) < 1e-6
