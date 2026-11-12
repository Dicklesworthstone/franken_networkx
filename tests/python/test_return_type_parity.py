"""Return-type parity with networkx.

Return-type divergences are subtle drop-in breaks — code that does integer math
on a result, or indexes a tuple, breaks if fnx returns a float where nx returns
an int (or a list for a tuple). A transitivity empty-graph int-vs-float return
was a real bug in this codebase. This pins the result TYPE (scalar type and
dict value type) across normal and degenerate graphs.

RAISING is part of the return contract. Comparing types only where BOTH calls
succeed leaves the interesting half unasserted: 4 of the 60 scalar (function,
shape) pairs raise in both libraries and were skipped silently, and a future
divergence where one starts succeeding while the other still raises would also
have passed. The comparison below is on the full outcome — the returned type
when it returns, the exception type when it raises — so all 60 are checked.

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


def _outcome(fn, g):
    """What the call DID: the returned type, or the exception type it raised."""
    try:
        return ("returned", type(fn(g)).__name__)
    except Exception as exc:  # noqa: BLE001 - the type IS the assertion
        return ("raised", type(exc).__name__)


def _pair(shape):
    edges, n = _SHAPES[shape]
    fg = fnx.Graph(); fg.add_nodes_from(range(n)); fg.add_edges_from(edges)
    ng = nx.Graph(); ng.add_nodes_from(range(n)); ng.add_edges_from(edges)
    return fg, ng


@pytest.mark.parametrize("shape", list(_SHAPES))
@pytest.mark.parametrize("name", _SCALAR_FUNCS)
def test_scalar_return_type(name, shape):
    fg, ng = _pair(shape)

    f = _outcome(getattr(fnx, name), fg)
    n = _outcome(getattr(nx, name), ng)
    # Full outcome, not just the both-succeeded case: whether it raises is as
    # much a part of the contract as what it returns, and int vs float matters.
    assert f == n, f"{name} on {shape}: fnx={f} nx={n}"


@pytest.mark.parametrize("shape", list(_SHAPES))
@pytest.mark.parametrize("name", _DICT_FUNCS)
def test_dict_value_type(name, shape):
    """Every shape, and every VALUE — not the first value of one shape.

    Reading only `next(iter(values))` samples one entry, and on the degenerate
    shapes there may be no entry at all to sample.
    """
    fg, ng = _pair(shape)
    fd = getattr(fnx, name)(fg)
    nd = getattr(nx, name)(ng)

    assert type(fd).__name__ == type(nd).__name__
    assert set(fd) == set(nd)                     # same keys, so the same nodes
    for key in nd:
        assert type(fd[key]).__name__ == type(nd[key]).__name__, f"{name}/{shape}/{key}"
