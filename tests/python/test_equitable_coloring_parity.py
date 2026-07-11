"""Differential + golden parity for equitable graph coloring.

``equitable_color(G, num_colors)`` returns an equitable coloring (color
class sizes differ by at most one) when ``num_colors > max_degree``;
``is_equitable`` validates a coloring. Neither had a dedicated test file.

br-r37-c1-1k6jy
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx
from franken_networkx.algorithms.coloring.equitable_coloring import (
    is_equitable as fnx_is_equitable,
)
from networkx.algorithms.coloring.equitable_coloring import (
    is_equitable as nx_is_equitable,
)


def _pair(seed, p=0.3):
    rng = random.Random(seed)
    n = rng.randint(6, 12)
    fg = fnx.Graph()
    ng = nx.Graph()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if rng.random() < p:
                fg.add_edge(u, v)
                ng.add_edge(u, v)
    return fg, ng, n


@pytest.mark.parametrize("seed", range(50))
def test_equitable_color_matches_networkx(seed):
    fg, ng, _ = _pair(seed)
    max_degree = max((d for _, d in ng.degree()), default=0)
    num_colors = max_degree + 1
    fr = fnx.equitable_color(fg, num_colors)
    nr = nx.equitable_color(ng, num_colors)
    assert list(fr.items()) == list(nr.items())
    # The coloring fnx returns is a valid equitable coloring per nx.
    assert nx_is_equitable(ng, fr)


@pytest.mark.parametrize("seed", range(40))
def test_is_equitable_matches_networkx(seed):
    fg, ng, n = _pair(seed)
    rng = random.Random(seed * 7 + 1)
    coloring = {i: rng.randint(0, 2) for i in range(n)}
    assert fnx_is_equitable(fg, coloring) == nx_is_equitable(ng, coloring)


def test_equitable_color_golden():
    # K4 needs 4 colors; each node gets a distinct color.
    fr = fnx.equitable_color(fnx.complete_graph(4), 4)
    assert len(set(fr.values())) == 4
    assert fr == nx.equitable_color(nx.complete_graph(4), 4)


def test_too_few_colors_raises_like_networkx():
    with pytest.raises(nx.NetworkXAlgorithmError):
        fnx.equitable_color(fnx.complete_graph(4), 2)
    with pytest.raises(nx.NetworkXAlgorithmError):
        nx.equitable_color(nx.complete_graph(4), 2)


def test_exact_graph_snapshot_preserves_single_padding_quirk():
    edges = [(0, 3), (0, 4), (1, 2), (1, 4)]
    fg = fnx.Graph()
    ng = nx.Graph()
    fg.add_nodes_from(range(5))
    ng.add_nodes_from(range(5))
    fg.add_edges_from(edges)
    ng.add_edges_from(edges)

    fr = fnx.equitable_color(fg, 3)
    nr = nx.equitable_color(ng, 3)
    assert list(fr.items()) == list(nr.items())
    assert fr == {0: 0, 1: 2, 2: 0, 3: 1, 4: 1}


def test_exact_graph_snapshot_preserves_multi_node_padding_clique():
    fg = fnx.cycle_graph(4)
    ng = nx.cycle_graph(4)
    fr = fnx.equitable_color(fg, 3)
    nr = nx.equitable_color(ng, 3)
    assert list(fr.items()) == list(nr.items())


def test_exact_graph_snapshot_counts_self_loop_degree_twice():
    fg = fnx.Graph()
    ng = nx.Graph()
    fg.add_edge("loop", "loop")
    ng.add_edge("loop", "loop")

    with pytest.raises(nx.NetworkXAlgorithmError) as fr_error:
        fnx.equitable_color(fg, 2)
    with pytest.raises(nx.NetworkXAlgorithmError) as nr_error:
        nx.equitable_color(ng, 2)
    assert str(fr_error.value) == str(nr_error.value)

    fr = fnx.equitable_color(fg, 3)
    nr = nx.equitable_color(ng, 3)
    assert list(fr.items()) == list(nr.items())


def test_exact_graph_snapshot_preserves_mixed_node_display_order():
    nodes = [("tuple", 1), "alpha", 7, 2.5, "isolate"]
    edges = [(nodes[0], nodes[2]), (nodes[2], nodes[1]), (nodes[1], nodes[3])]
    fg = fnx.Graph()
    ng = nx.Graph()
    fg.add_nodes_from(nodes)
    ng.add_nodes_from(nodes)
    fg.add_edges_from(edges)
    ng.add_edges_from(edges)

    fr = fnx.equitable_color(fg, 3)
    nr = nx.equitable_color(ng, 3)
    assert list(fr.items()) == list(nr.items())


def test_exact_graph_snapshot_avoids_relabel_copy(monkeypatch):
    fg = fnx.path_graph(7)
    ng = nx.path_graph(7)
    expected = nx.equitable_color(ng, 3)

    def fail_relabel(*_args, **_kwargs):
        pytest.fail("exact Graph snapshot path called relabel_nodes")

    monkeypatch.setattr(fnx, "relabel_nodes", fail_relabel)
    result = fnx.equitable_color(fg, 3)
    assert list(result.items()) == list(expected.items())


def test_exact_graph_snapshot_ignores_shadowed_native_hook():
    fg = fnx.path_graph(4)
    ng = nx.path_graph(4)
    fg._native_adjacency_keys = lambda: []

    result = fnx.equitable_color(fg, 3)
    expected = nx.equitable_color(ng, 3)
    assert list(result.items()) == list(expected.items())


def test_graph_subclass_preserves_fallback_ordered_parity():
    class DerivedGraph(fnx.Graph):
        pass

    nodes = ["z", 3, ("x", 1), "isolate"]
    edges = [(nodes[0], nodes[1]), (nodes[1], nodes[2])]
    fg = DerivedGraph()
    ng = nx.Graph()
    fg.add_nodes_from(nodes)
    ng.add_nodes_from(nodes)
    fg.add_edges_from(edges)
    ng.add_edges_from(edges)

    result = fnx.equitable_color(fg, 3)
    expected = nx.equitable_color(ng, 3)
    assert list(result.items()) == list(expected.items())
