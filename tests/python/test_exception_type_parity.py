"""Exception-TYPE parity on invalid / edge-case inputs.

Drop-in callers rely on ``except nx.SomeError`` catching the right thing.
networkx raises specific types — ``NetworkXUnfeasible`` on a cyclic
topological sort, ``AmbiguousSolution`` on disconnected spectral centrality,
``PowerIterationFailedConvergence`` on non-converged power iteration,
``NetworkXNoPath`` / ``NodeNotFound`` / ``NetworkXNotImplemented`` /
``NetworkXPointlessConcept`` / ``ZeroDivisionError`` in their respective
cases. A port that raises a generic or wrong type silently breaks those
callers. This pins the raised exception *type* (not message) to networkx's
across a battery of invalid inputs, complementing the value-sensitivity nets.
"""

import networkx as nx
import franken_networkx as fnx

import pytest


def _exc_type(fn):
    try:
        fn()
        return "NOEXC"
    except Exception as exc:  # noqa: BLE001 — comparing the type is the point
        return type(exc).__name__


def _U(mod):
    return mod.Graph([(0, 1), (1, 2), (2, 3), (3, 0), (0, 2)])


def _DISC(mod):
    return mod.Graph([(0, 1), (2, 3)])


def _DICYC(mod):
    return mod.DiGraph([(0, 1), (1, 0)])


# label -> (nx_callable, fnx_callable). Each should raise (or not) identically.
_CASES = {
    # convergence
    "pagerank_noconv": (lambda: nx.pagerank(_U(nx), max_iter=1), lambda: fnx.pagerank(_U(fnx), max_iter=1)),
    "eigenvector_noconv": (lambda: nx.eigenvector_centrality(_U(nx), max_iter=1), lambda: fnx.eigenvector_centrality(_U(fnx), max_iter=1)),
    "katz_noconv": (lambda: nx.katz_centrality(_U(nx), max_iter=1), lambda: fnx.katz_centrality(_U(fnx), max_iter=1)),
    # ambiguous / disconnected spectral
    "eigenvector_numpy_disconnected": (lambda: nx.eigenvector_centrality_numpy(_DISC(nx)), lambda: fnx.eigenvector_centrality_numpy(_DISC(fnx))),
    "eigenvector_numpy_empty": (lambda: nx.eigenvector_centrality_numpy(nx.Graph()), lambda: fnx.eigenvector_centrality_numpy(fnx.Graph())),
    "fiedler_disconnected": (lambda: nx.fiedler_vector(_DISC(nx)), lambda: fnx.fiedler_vector(_DISC(fnx))),
    # cyclic where a DAG is required
    "topo_sort_cyclic": (lambda: list(nx.topological_sort(_DICYC(nx))), lambda: list(fnx.topological_sort(_DICYC(fnx)))),
    "dag_longest_cyclic": (lambda: nx.dag_longest_path(_DICYC(nx)), lambda: fnx.dag_longest_path(_DICYC(fnx))),
    "transitive_reduction_cyclic": (lambda: nx.transitive_reduction(_DICYC(nx)), lambda: fnx.transitive_reduction(_DICYC(fnx))),
    # connectivity required
    "diameter_disconnected": (lambda: nx.diameter(_DISC(nx)), lambda: fnx.diameter(_DISC(fnx))),
    "radius_disconnected": (lambda: nx.radius(_DISC(nx)), lambda: fnx.radius(_DISC(fnx))),
    "eccentricity_disconnected": (lambda: nx.eccentricity(_DISC(nx)), lambda: fnx.eccentricity(_DISC(fnx))),
    "diameter_empty": (lambda: nx.diameter(nx.Graph()), lambda: fnx.diameter(fnx.Graph())),
    "avg_shortest_path_disconnected": (lambda: nx.average_shortest_path_length(_DISC(nx)), lambda: fnx.average_shortest_path_length(_DISC(fnx))),
    "avg_shortest_path_empty": (lambda: nx.average_shortest_path_length(nx.Graph()), lambda: fnx.average_shortest_path_length(fnx.Graph())),
    # negative weights
    "dijkstra_negative": (
        lambda: nx.single_source_dijkstra_path_length(nx.Graph([(0, 1, {"weight": -2})]), 0, weight="weight"),
        lambda: fnx.single_source_dijkstra_path_length(fnx.Graph([(0, 1, {"weight": -2})]), 0, weight="weight"),
    ),
    "bellman_neg_cycle": (
        lambda: nx.single_source_bellman_ford_path_length(nx.DiGraph([(0, 1, {"weight": -1}), (1, 0, {"weight": -1})]), 0, weight="weight"),
        lambda: fnx.single_source_bellman_ford_path_length(fnx.DiGraph([(0, 1, {"weight": -1}), (1, 0, {"weight": -1})]), 0, weight="weight"),
    ),
    # no path / missing node
    "shortest_path_no_path": (lambda: nx.shortest_path(_DISC(nx), 0, 3), lambda: fnx.shortest_path(_DISC(fnx), 0, 3)),
    "astar_no_path": (lambda: nx.astar_path(_DISC(nx), 0, 3), lambda: fnx.astar_path(_DISC(fnx), 0, 3)),
    "shortest_path_missing_src": (lambda: nx.shortest_path(_U(nx), 99, 0), lambda: fnx.shortest_path(_U(fnx), 99, 0)),
    "clustering_missing_node": (lambda: nx.clustering(_U(nx), 99), lambda: fnx.clustering(_U(fnx), 99)),
    # not implemented for graph type
    "triangles_directed": (lambda: nx.triangles(nx.DiGraph([(0, 1)])), lambda: fnx.triangles(fnx.DiGraph([(0, 1)]))),
    "is_chordal_directed": (lambda: nx.is_chordal(nx.DiGraph([(0, 1)])), lambda: fnx.is_chordal(fnx.DiGraph([(0, 1)]))),
    "find_cliques_directed": (lambda: list(nx.find_cliques(nx.DiGraph([(0, 1)]))), lambda: list(fnx.find_cliques(fnx.DiGraph([(0, 1)])))),
    # bipartite on non-bipartite
    "bipartite_sets_nonbip": (lambda: nx.bipartite.sets(_U(nx)), lambda: fnx.bipartite.sets(_U(fnx))),
    "bipartite_color_nonbip": (lambda: nx.bipartite.color(nx.complete_graph(3)), lambda: fnx.bipartite.color(fnx.complete_graph(3))),
    # zero-edge / empty special
    "modularity_empty": (lambda: nx.community.modularity(nx.Graph(), []), lambda: fnx.community.modularity(fnx.Graph(), [])),
}


@pytest.mark.parametrize("label", sorted(_CASES))
def test_exception_type_matches_networkx(label):
    nx_fn, fnx_fn = _CASES[label]
    nx_type = _exc_type(nx_fn)
    fnx_type = _exc_type(fnx_fn)
    assert fnx_type == nx_type, f"{label}: networkx raised {nx_type}, franken_networkx raised {fnx_type}"
