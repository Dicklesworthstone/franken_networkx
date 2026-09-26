"""br-r37-c1-apelp - a lazy iterable passed to remove_nodes_from / remove_edges_from that
reads the graph sees every removal made before it, as in networkx.

networkx removes each item before pulling the next, so a filter on degree or on
number_of_edges sees the graph as the removals leave it:

    G = path_graph(6); G.remove_nodes_from(n for n in [0, 1, 2, 5] if G.degree(n) <= 1)
    networkx keeps [2, 3, 4] ... fnx kept [1, 2, 3, 4]

fnx buffered the iterable first (br-rmvbunch), so it read the graph as it was before
the call - 18 of the 44 rows below diverged. The removal wrappers now route an
iterable that can reach the graph (imddi's _ebunch_reads_graph) through per-item
removal. That includes a generator iterating the very graph it removes from, where
networkx either finishes with a partial result or raises RuntimeError part way - the
rows pin fnx to the same outcome.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph")
EDGES = [(0, 1), (0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 0), (2, 5)]


def nodes_path_degree(G):
    G.clear()
    G.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 4), (4, 5)])
    G.remove_nodes_from(n for n in [0, 1, 2, 5] if G.degree(n) <= 1)


def edges_star_degree(G):
    G.clear()
    G.add_edges_from([(0, 1), (0, 2), (0, 3), (0, 4)])
    G.remove_edges_from(e for e in [(0, 1), (0, 2), (0, 3), (0, 4)] if G.degree(0) > 2)


def nodes_degree_filter(G):
    G.remove_nodes_from(n for n in [0, 1, 2, 5] if G.degree(n) <= 1)


def nodes_iterating_self(G):
    G.remove_nodes_from(n for n in G if G.degree(n) <= 1)


def nodes_list_of_self(G):
    G.remove_nodes_from(list(n for n in G if G.degree(n) <= 1))


def edges_degree_filter(G):
    G.remove_edges_from(e for e in [(0, 1), (1, 2), (2, 3), (3, 4)] if G.degree(e[0]) > 1)


def edges_parallel_count_filter(G):
    G.remove_edges_from(e for e in [(0, 1), (0, 1), (1, 2)] if G.number_of_edges(*e) > 1)


def edges_iterating_self(G):
    G.remove_edges_from(e for e in G.edges() if G.degree(e[0]) > 1)


def nodes_filter_lambda(G):
    G.remove_nodes_from(filter(lambda n: G.degree(n) <= 1, [0, 1, 2, 5]))


def nodes_plain_generator(G):
    G.remove_nodes_from(n for n in [0, 5, 99])


def edges_raising_generator(G):
    def gen():
        yield (0, 1)
        if G.has_edge(1, 2):
            yield (1, 2)
        raise KeyError("boom")

    G.remove_edges_from(gen())


IDIOMS = [
    nodes_path_degree, edges_star_degree, nodes_degree_filter, nodes_iterating_self,
    nodes_list_of_self, edges_degree_filter, edges_parallel_count_filter, edges_iterating_self,
    nodes_filter_lambda, nodes_plain_generator, edges_raising_generator,
]


def _state(lib, cls, idiom):
    G = getattr(lib, cls)()
    G.add_edges_from(EDGES)
    try:
        idiom(G)
        error = None
    except Exception as exc:  # noqa: BLE001 - the exception is part of the compared state
        error = (type(exc).__name__, str(exc))
    edges = G.edges(keys=True) if G.is_multigraph() else G.edges()
    return error, sorted(map(repr, G.nodes)), sorted(map(repr, edges))


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("idiom", IDIOMS, ids=lambda f: f.__name__)
def test_graph_reading_iterable_removal_matches_networkx(idiom, cls):
    assert _state(fnx, cls, idiom) == _state(nx, cls, idiom)


@pytest.mark.parametrize(("k", "graph"), [(2, nx.complete_graph(6)), (1, nx.petersen_graph()),
                                          (2, nx.complete_bipartite_graph(4, 4))])
def test_k_factor_which_removes_while_iterating_matches_networkx(k, graph):
    # fnx's k_factor, like networkx's, removes with a generator over g.edges - the
    # one internal caller the new routing sends per-item.
    expected = sorted(tuple(sorted(e)) for e in nx.k_factor(nx.Graph(graph), k).edges())
    actual = sorted(tuple(sorted(e)) for e in fnx.k_factor(fnx.Graph(graph), k).edges())
    assert actual == expected
