"""Return-type parity with networkx.

Return-type divergences are subtle drop-in breaks — code that does integer math
on a result, or indexes a tuple, breaks if fnx returns a float where nx returns
an int (or a list for a tuple). A transitivity empty-graph int-vs-float return
was a real bug in this codebase. This pins the result TYPE (scalar type and
dict value type) across normal and degenerate graphs.

No mocks: real fnx and real networkx.
"""

from __future__ import annotations

import pytest
import networkx as nx
import franken_networkx as fnx

_SCALAR_FUNCS = [
    "density", "transitivity", "average_clustering", "number_connected_components",
    "number_of_isolates", "global_efficiency", "s_metric", "number_of_nodes",
    "number_of_edges", "node_connectivity", "edge_connectivity", "wiener_index",
]

_DICT_FUNCS = [
    "clustering", "triangles", "core_number", "pagerank", "degree_centrality",
    "closeness_centrality", "betweenness_centrality", "square_clustering",
]

_SHAPES = {
    "empty": ([], 0),
    "single": ([], 1),
    "one_edge": ([(0, 1)], 2),
    "triangle": ([(0, 1), (1, 2), (2, 0)], 3),
    "normal": ([(0, 1), (1, 2), (2, 3), (3, 4), (4, 0), (0, 2), (1, 3)], 5),
}


def _pair(shape):
    edges, n = _SHAPES[shape]
    fg = fnx.Graph(); fg.add_nodes_from(range(n)); fg.add_edges_from(edges)
    ng = nx.Graph(); ng.add_nodes_from(range(n)); ng.add_edges_from(edges)
    return fg, ng


@pytest.mark.parametrize("shape", list(_SHAPES))
@pytest.mark.parametrize("name", _SCALAR_FUNCS)
def test_scalar_return_type(name, shape):
    fg, ng = _pair(shape)

    def outcome(fn, g):
        try:
            return ("ok", type(fn(g)).__name__)
        except Exception:  # noqa: BLE001
            return ("err", None)

    f = outcome(getattr(fnx, name), fg)
    n = outcome(getattr(nx, name), ng)
    # Where both succeed, the result type must match (int vs float matters).
    if f[0] == "ok" and n[0] == "ok":
        assert f[1] == n[1], f"{name} on {shape}: fnx={f[1]} nx={n[1]}"


@pytest.mark.parametrize("name", _DICT_FUNCS)
def test_dict_value_type(name):
    fg, ng = _pair("normal")
    fd = getattr(fnx, name)(fg)
    nd = getattr(nx, name)(ng)
    assert type(fd).__name__ == type(nd).__name__
    fv = next(iter(fd.values()))
    nv = next(iter(nd.values()))
    assert type(fv).__name__ == type(nv).__name__
