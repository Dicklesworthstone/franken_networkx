"""Weights the native store cannot hold as numbers (br-r37-c1-6eaq6).

The attribute store's int is an i64. An int wider than that used to be stored
as its float - `extract::<f64>()` succeeds, rounded - so every native reader
computed on a number networkx never sees: minimum_spanning_tree handed out
9.223372036854776e+18 for 2**63, weighted degrees summed to floats, and
10**20 + 1 tied with 10**20 in betweenness. The store now keeps an opaque
stand-in for such an int, as for a tuple or None, and the readers that met one
as the default weight 1 (the spanning-tree kernels) now take networkx's route,
which raises TypeError on a non-number. Int weights whose magnitudes total past
2**53 are exact too where a vectorised or collapsed f64 path added them
(floyd_warshall, the undirected multigraph Dijkstra and Bellman-Ford collapse).

No mocks: real fnx against real networkx, results compared with their types,
exceptions by type, on every graph class and three construction routes.
"""

from __future__ import annotations

import pytest
import networkx as nx
import franken_networkx as fnx

EDGES = [(0, 1), (1, 2), (2, 3), (3, 0), (1, 3)]
WEIGHTS = {
    "wide": [2**63, 10**20 + 1, -(2**70) + 3, 7, 10**20],
    "wide_positive": [2**63, 10**20 + 1, 2**70 + 3, 7, 10**20],
    "i64_past_2_53": [2**62, 3, 4, 5, 2**62 + 1],
    "tuple": [(1, 2), 3, 4, 5, 6],
    "none": [None, 3, 4, 5, 6],
}
CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
ROUTES = ["add_edge", "add_edges_from", "add_weighted_edges_from"]


def _build(lib, cls, route, weights):
    G = getattr(lib, cls)()
    edges = [(u, v, w) for (u, v), w in zip(EDGES, weights)]
    if route == "add_edge":
        for u, v, w in edges:
            G.add_edge(u, v, weight=w)
    elif route == "add_edges_from":
        G.add_edges_from((u, v, {"weight": w}) for u, v, w in edges)
    else:
        G.add_weighted_edges_from(edges)
    return G


def _typed(x):
    if hasattr(x, "edges") and hasattr(x, "nodes"):
        return sorted(
            repr((u, v, {k: (type(w).__name__, w) for k, w in d.items()}))
            for u, v, d in x.edges(data=True)
        )
    if isinstance(x, dict):
        return [(repr(k), _typed(v)) for k, v in x.items()]
    if isinstance(x, (list, tuple)) or hasattr(x, "__next__"):
        return [_typed(e) for e in x]
    return (type(x).__name__, repr(x))


FUNCTIONS = {
    "minimum_spanning_tree": lambda m, G: m.minimum_spanning_tree(G),
    "maximum_spanning_tree": lambda m, G: m.maximum_spanning_tree(G),
    "minimum_spanning_tree_prim": lambda m, G: m.minimum_spanning_tree(G, algorithm="prim"),
    "minimum_spanning_edges": lambda m, G: list(m.minimum_spanning_edges(G, data=True)),
    "maximum_spanning_edges_prim": lambda m, G: list(
        m.maximum_spanning_edges(G, algorithm="prim", data=True)
    ),
    "degree_weight": lambda m, G: list(G.degree(weight="weight")),
    "degree_weight_node": lambda m, G: G.degree(1, weight="weight"),
    "size_weight": lambda m, G: G.size(weight="weight"),
    "single_source_dijkstra_path_length": lambda m, G: m.single_source_dijkstra_path_length(G, 0),
    "shortest_path_length_weight": lambda m, G: m.shortest_path_length(G, 0, weight="weight"),
    "single_source_bellman_ford_path_length": lambda m, G: (
        m.single_source_bellman_ford_path_length(G, 0)
    ),
    "all_pairs_dijkstra_path_length": lambda m, G: dict(m.all_pairs_dijkstra_path_length(G)),
    "floyd_warshall": lambda m, G: {k: dict(v) for k, v in m.floyd_warshall(G).items()},
    "eccentricity_weight": lambda m, G: m.eccentricity(G, weight="weight"),
    "betweenness_centrality_weight": lambda m, G: m.betweenness_centrality(G, weight="weight"),
    "copy": lambda m, G: G.copy(),
    "edges_data_weight": lambda m, G: list(G.edges(data="weight")),
}


@pytest.mark.parametrize("weights", list(WEIGHTS), ids=list(WEIGHTS))
@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("name", list(FUNCTIONS))
def test_weighted_results_match_networkx_exactly(name, cls, route, weights):
    fn = FUNCTIONS[name]
    out = []
    for lib in (fnx, nx):
        G = _build(lib, cls, route, WEIGHTS[weights])
        try:
            out.append(_typed(fn(lib, G)))
        except Exception as exc:  # noqa: BLE001 - the exception type is the result
            out.append(("raise", type(exc).__name__))
    assert out[0] == out[1]


def test_wide_int_attribute_survives_a_store_backed_copy_of_the_tree():
    # The bead's minimal case: the tree's edge carries networkx's int object.
    for value in (2**63, 10**20 + 1, -(2**70)):
        G = fnx.Graph()
        G.add_edge(1, 2, weight=value)
        data = fnx.minimum_spanning_tree(G)[1][2]
        assert type(data["weight"]) is int and data["weight"] == value


def test_wide_int_subclass_weight_is_not_rounded():
    class Wide(int):
        pass

    graphs = {}
    for lib in (fnx, nx):
        G = graphs[lib] = lib.Graph()
        G.add_edge(0, 1, weight=Wide(10**20 + 1))
        G.add_edge(1, 2, weight=Wide(10**20))
    want = nx.single_source_dijkstra_path_length(graphs[nx], 0)
    got = fnx.single_source_dijkstra_path_length(graphs[fnx], 0)
    assert _typed(got) == _typed(want)
    assert got[2] == 2 * 10**20 + 1


@pytest.mark.parametrize("cls", ["Graph", "DiGraph"])
@pytest.mark.parametrize("route", ["numpy", "scipy_coo", "scipy_csr"])
def test_uint64_matrix_weights_preserve_python_integers(cls, route):
    import numpy as np
    from scipy import sparse

    matrix = np.array([[0, 2**63, 0], [0, 0, 3], [0, 0, 0]], dtype=np.uint64)
    graphs = {}
    for lib in (fnx, nx):
        if route == "numpy":
            graph = lib.from_numpy_array(matrix, create_using=getattr(lib, cls))
        else:
            constructor = sparse.coo_array if route == "scipy_coo" else sparse.csr_array
            graph = lib.from_scipy_sparse_array(
                constructor(matrix), create_using=getattr(lib, cls)
            )
        graphs[lib] = graph
        assert type(graph[0][1]["weight"]) is int
        assert graph[0][1]["weight"] == 2**63
        assert type(graph.copy()[0][1]["weight"]) is int
    for name in ("degree_weight", "single_source_dijkstra_path_length", "floyd_warshall"):
        assert _typed(FUNCTIONS[name](fnx, graphs[fnx])) == _typed(FUNCTIONS[name](nx, graphs[nx]))
    if cls == "Graph":
        assert _typed(fnx.minimum_spanning_tree(graphs[fnx])) == _typed(
            nx.minimum_spanning_tree(graphs[nx])
        )


@pytest.mark.parametrize("cls", [fnx.Graph, fnx.DiGraph])
def test_matrix_batch_declines_wide_value_without_partial_mutation(cls):
    graph = cls()
    assert not graph._native_fill_weighted_int_edges(
        3, iter([0, 1]), iter([1, 2]), iter([3, 2**63]), "weight"
    )
    assert list(graph.nodes) == []
    assert list(graph.edges) == []
