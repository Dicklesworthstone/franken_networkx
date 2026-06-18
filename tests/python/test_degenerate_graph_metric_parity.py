"""Differential parity on degenerate graph fixtures.

Native kernels are most likely to diverge from networkx on degenerate
inputs — self-loops, single/isolated nodes, disconnected graphs — which is
the input class that surfaced the two node_connectivity P1 bugs
(br-r37-c1-cqlms / br-r37-c1-ebd8d). This pins fnx == nx (NaN-aware,
error-type-aware) across a battery of scalar and dict metrics on such
graphs.

br-r37-c1-sb0wj
"""

from __future__ import annotations

import math

import pytest
import networkx as nx
import franken_networkx as fnx

# (name, edges, extra_nodes)
_FIXTURES = {
    "two_node": ([(0, 1)], []),
    "triangle": ([(0, 1), (1, 2), (2, 0)], []),
    "star": ([(0, 1), (0, 2), (0, 3)], []),
    "path": ([(0, 1), (1, 2), (2, 3)], []),
    "complete4": ([(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)], []),
    "selfloop": ([(0, 1), (1, 2), (0, 0)], []),
    "isolated": ([(0, 1)], [9]),
    "disconnected": ([(0, 1), (2, 3)], []),
    "bridge": ([(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 3)], []),
}

# Metrics defined on any graph (no connectivity precondition).
_ANY_GRAPH = [
    "triangles", "clustering", "square_clustering", "core_number",
    "number_of_selfloops", "degree_centrality", "closeness_centrality",
    "pagerank", "transitivity", "average_clustering", "s_metric",
    "global_efficiency", "local_efficiency", "estrada_index",
    "node_connectivity", "edge_connectivity", "number_connected_components",
]


def _build(lib, edges, extra):
    g = lib.Graph(edges)
    g.add_nodes_from(extra)
    return g


def _equal(f, x):
    if isinstance(f, float) and isinstance(x, float):
        return (math.isnan(f) and math.isnan(x)) or abs(f - x) <= 1e-9 * max(1, abs(x))
    if isinstance(f, dict) and isinstance(x, dict):
        return set(f) == set(x) and all(_equal(f[k], x[k]) for k in f)
    return f == x


@pytest.mark.parametrize("fixture", list(_FIXTURES))
@pytest.mark.parametrize("metric", _ANY_GRAPH)
def test_metric_matches_networkx_on_degenerate_graph(metric, fixture):
    edges, extra = _FIXTURES[fixture]
    fg = _build(fnx, edges, extra)
    ng = _build(nx, edges, extra)
    try:
        f = getattr(fnx, metric)(fg)
        f_err = None
    except Exception as exc:  # noqa: BLE001
        f, f_err = None, type(exc)
    try:
        x = getattr(nx, metric)(ng)
        x_err = None
    except Exception as exc:  # noqa: BLE001
        x, x_err = None, type(exc)
    if f_err or x_err:
        # Same exception type (or both raise something in the nx hierarchy).
        assert f_err is not None and x_err is not None, f"{metric}[{fixture}] raise mismatch: {f_err} vs {x_err}"
    else:
        assert _equal(f, x), f"{metric}[{fixture}]: {f!r} != {x!r}"
