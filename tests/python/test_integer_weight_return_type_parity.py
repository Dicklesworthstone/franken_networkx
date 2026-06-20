"""Int-vs-float return-type parity on integer-weighted graphs.

networkx preserves Python ``int`` when all contributing weights are int (a
sum/distance of ints stays int); the Rust kernels naturally produce ``float``.
This has been a real bug surface — e.g. astar_path_length
(br-r37-c1-astarlen-int) and dag_longest_path_length (br-r37-c1-oqspv) both
needed explicit int-preservation. This net runs weight-summing /
distance-returning functions on an integer-weighted graph and asserts the
returned scalar / dict-value types match networkx exactly (int stays int,
float stays float).
"""

import networkx as nx
import franken_networkx as fnx

import pytest


def _iwg(mod, directed=False):
    g = (mod.DiGraph if directed else mod.Graph)()
    edges = [(0, 1, 2), (1, 2, 3), (2, 3, 1), (3, 0, 4), (0, 2, 2), (2, 4, 5), (4, 5, 1), (1, 4, 3)]
    for u, v, w in edges:
        g.add_edge(u, v, weight=w)
    if directed:
        for u, v, w in [(5, 0, 2), (3, 1, 1)]:
            g.add_edge(u, v, weight=w)
    return g


def _dict_types_match(dn, df):
    assert set(dn) == set(df)
    for k in dn:
        assert type(df[k]) is type(dn[k]), f"node {k}: nx={type(dn[k]).__name__} fnx={type(df[k]).__name__}"
        assert df[k] == dn[k]


# scalar-returning functions (int weights -> int in nx)
_SCALAR = {
    "size_weighted": lambda m, g: g.size(weight="weight"),
    "shortest_path_length": lambda m, g: m.shortest_path_length(g, 0, 5, weight="weight"),
    "dijkstra_path_length": lambda m, g: m.dijkstra_path_length(g, 0, 5, weight="weight"),
    "bellman_ford_path_length": lambda m, g: m.bellman_ford_path_length(g, 0, 5, weight="weight"),
    "astar_path_length": lambda m, g: m.astar_path_length(g, 0, 5, weight="weight"),
    "diameter_weighted": lambda m, g: m.diameter(g, weight="weight"),
    "radius_weighted": lambda m, g: m.radius(g, weight="weight"),
    "wiener_index_weighted": lambda m, g: m.wiener_index(g, weight="weight"),
}


@pytest.mark.parametrize("name", sorted(_SCALAR))
def test_scalar_int_weight_type_matches_networkx(name):
    fn = _SCALAR[name]
    vn, vf = fn(nx, _iwg(nx)), fn(fnx, _iwg(fnx))
    assert type(vf) is type(vn), f"{name}: nx={type(vn).__name__} fnx={type(vf).__name__}"
    assert vf == vn


_DICT = {
    "degree_weighted": lambda m, g: dict(g.degree(weight="weight")),
    "dijkstra_combined_all": lambda m, g: dict(m.single_source_dijkstra(g, 0, weight="weight")[0]),
    "dijkstra_path_length_all": lambda m, g: dict(m.single_source_dijkstra_path_length(g, 0, weight="weight")),
    "bellman_path_length_all": lambda m, g: dict(m.single_source_bellman_ford_path_length(g, 0, weight="weight")),
    "eccentricity_weighted": lambda m, g: m.eccentricity(g, weight="weight"),
    "triangles": lambda m, g: m.triangles(g),
    "core_number": lambda m, g: m.core_number(g),
}


@pytest.mark.parametrize("name", sorted(_DICT))
def test_dict_int_weight_type_matches_networkx(name):
    fn = _DICT[name]
    _dict_types_match(fn(nx, _iwg(nx)), fn(fnx, _iwg(fnx)))


def test_max_flow_value_int_capacity_type():
    def build(mod):
        g = mod.DiGraph()
        for u, v, c in [(0, 1, 3), (0, 2, 2), (1, 3, 2), (2, 3, 3), (1, 2, 1), (3, 4, 4), (0, 4, 1)]:
            g.add_edge(u, v, capacity=c)
        return g
    vn = nx.maximum_flow_value(build(nx), 0, 4)
    vf = fnx.maximum_flow_value(build(fnx), 0, 4)
    assert type(vf) is type(vn) and vf == vn


def test_unweighted_distance_is_int():
    gn = nx.path_graph(6)
    gf = fnx.path_graph(6)
    dn = dict(nx.single_source_shortest_path_length(gn, 0))
    df = dict(fnx.single_source_shortest_path_length(gf, 0))
    _dict_types_match(dn, df)
    assert all(type(v) is int for v in df.values())
