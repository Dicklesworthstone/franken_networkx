"""Phase B certification: chordal graphs, tournament algorithms,
advanced connectivity (k_components, all_node_cuts), and greedy_color
across all strategies (the non-default ones are set-iteration-order
bound and must delegate — verified they match nx). Zero divergences.
"""
import random

import networkx as nx
import networkx.algorithms.tournament as nxt
import pytest

import franken_networkx as fnx


def _chordal(mod):
    g = mod.Graph()
    for u, v in [(0, 1), (1, 2), (0, 2), (2, 3), (2, 4), (3, 4), (4, 5), (4, 6), (5, 6), (0, 3)]:
        g.add_edge(u, v)
    return g


def test_chordal_family():
    cf, cn = _chordal(fnx), _chordal(nx)
    assert fnx.is_chordal(cf) == nx.is_chordal(cn) is True
    assert nx.chordal_graph_treewidth(cf) == nx.chordal_graph_treewidth(cn)
    assert sorted(sorted(repr(x) for x in c) for c in nx.chordal_graph_cliques(cf)) == sorted(
        sorted(repr(x) for x in c) for c in nx.chordal_graph_cliques(cn)
    )
    assert fnx.is_chordal(fnx.cycle_graph(5)) == nx.is_chordal(nx.cycle_graph(5)) is False


def _tour(mod):
    R = random.Random(61)
    g = mod.DiGraph()
    for i in range(8):
        for j in range(i + 1, 8):
            g.add_edge(i, j) if R.random() < 0.5 else g.add_edge(j, i)
    return g


def test_tournament():
    tf, tn = _tour(fnx), _tour(nx)
    assert nxt.is_tournament(tf) == nxt.is_tournament(tn) is True
    assert nxt.score_sequence(tf) == nxt.score_sequence(tn)
    assert [repr(x) for x in nxt.hamiltonian_path(tf)] == [repr(x) for x in nxt.hamiltonian_path(tn)]


def _mk():
    R = random.Random(67)
    ue = [(u, v) for u, v in ((R.randrange(12), R.randrange(12)) for _ in range(45)) if u != v]
    return fnx.Graph(ue), nx.Graph(ue)


def test_advanced_connectivity():
    gf, gn = _mk()
    assert {k: sorted(sorted(repr(x) for x in c) for c in v) for k, v in nx.k_components(gf).items()} == {
        k: sorted(sorted(repr(x) for x in c) for c in v) for k, v in nx.k_components(gn).items()
    }
    assert fnx.node_connectivity(gf) == nx.node_connectivity(gn)
    assert sorted(len(c) for c in nx.all_node_cuts(gf)) == sorted(len(c) for c in nx.all_node_cuts(gn))


@pytest.mark.parametrize(
    "strategy",
    [
        "largest_first",
        "smallest_last",
        "independent_set",
        "connected_sequential_bfs",
        "connected_sequential_dfs",
        "saturation_largest_first",
    ],
)
def test_greedy_color_strategies(strategy):
    gf, gn = _mk()
    assert sorted((repr(k), v) for k, v in fnx.greedy_color(gf, strategy=strategy).items()) == sorted(
        (repr(k), v) for k, v in nx.greedy_color(gn, strategy=strategy).items()
    ), strategy
