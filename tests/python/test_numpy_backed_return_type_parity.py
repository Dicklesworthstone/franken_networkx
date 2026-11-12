"""Return-type parity for numpy-backed numeric functions: dict values and
scalars must be Python ``float`` (or ``int``), never leaked numpy scalars.

current_flow_closeness_centrality / information_centrality leaked ``np.float64``
dict values (br-r37-c1-cfctype) because they built the result straight from a
numpy array. np.float64 subclasses float so isinstance passes, but
``type(v) is float`` fails and repr differs. This net pins exact Python scalar
types across the numpy-backed centralities and scalar metrics so a future
numpy leak is caught (and stays json/repr-clean).
"""

import networkx as nx
import franken_networkx as fnx

import pytest


def _graph(mod):
    return mod.Graph([(0, 1), (1, 2), (2, 3), (3, 0), (0, 2), (2, 4)])


# dict-returning numeric functions whose values must be Python float.
_DICT_FLOAT = {
    "current_flow_betweenness_centrality": lambda m, g: m.current_flow_betweenness_centrality(g),
    "current_flow_closeness_centrality": lambda m, g: m.current_flow_closeness_centrality(g),
    "information_centrality": lambda m, g: m.information_centrality(g),
    "communicability_betweenness_centrality": lambda m, g: m.communicability_betweenness_centrality(g),
    "subgraph_centrality": lambda m, g: m.subgraph_centrality(g),
    "subgraph_centrality_exp": lambda m, g: m.subgraph_centrality_exp(g),
    "second_order_centrality": lambda m, g: m.second_order_centrality(g),
    "eigenvector_centrality_numpy": lambda m, g: m.eigenvector_centrality_numpy(g),
    "katz_centrality_numpy": lambda m, g: m.katz_centrality_numpy(g),
    "pagerank": lambda m, g: m.pagerank(g),
    "betweenness_centrality": lambda m, g: m.betweenness_centrality(g),
    "closeness_centrality": lambda m, g: m.closeness_centrality(g),
    "load_centrality": lambda m, g: m.load_centrality(g),
    "clustering": lambda m, g: m.clustering(g),
}


@pytest.mark.parametrize("name", sorted(_DICT_FLOAT))
def test_dict_values_are_python_float_like_networkx(name):
    fn = _DICT_FLOAT[name]
    if not (hasattr(nx, name) and hasattr(fnx, name)):
        pytest.skip(f"{name} unavailable")
    rn = fn(nx, _graph(nx))
    rf = fn(fnx, _graph(fnx))
    assert set(rn) == set(rf)
    for k in rn:
        # match nx's exact scalar type (nx returns int 0 for some zero-valued
        # entries, e.g. clustering of a degree-1 node) AND ensure it is a
        # native Python numeric, never a leaked numpy scalar.
        assert type(rf[k]) is type(rn[k]), f"{name}[{k}]: nx={type(rn[k]).__name__} fnx={type(rf[k]).__name__}"
        assert type(rf[k]) in (float, int), f"{name}[{k}] is {type(rf[k]).__name__} (numpy leak?)"


_SCALAR_FLOAT = {
    "algebraic_connectivity": lambda m, g: m.algebraic_connectivity(g),
    "estrada_index": lambda m, g: m.estrada_index(g),
    "global_efficiency": lambda m, g: m.global_efficiency(g),
    "transitivity": lambda m, g: m.transitivity(g),
    "average_clustering": lambda m, g: m.average_clustering(g),
}


@pytest.mark.parametrize("name", sorted(_SCALAR_FLOAT))
def test_scalar_is_python_float_like_networkx(name):
    fn = _SCALAR_FLOAT[name]
    if not (hasattr(nx, name) and hasattr(fnx, name)):
        pytest.skip(f"{name} unavailable")
    vn = fn(nx, _graph(nx))
    vf = fn(fnx, _graph(fnx))
    assert type(vf) is type(vn) is float, f"{name}: nx={type(vn).__name__} fnx={type(vf).__name__}"


def test_current_flow_closeness_json_roundtrips_without_numpy():
    import json
    r = fnx.current_flow_closeness_centrality(_graph(fnx))
    assert all(type(v) is float for v in r.values())
    assert json.loads(json.dumps(r)) == {str(k): v for k, v in r.items()}
