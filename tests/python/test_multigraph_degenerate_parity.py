"""Differential parity for multigraph metrics on degenerate fixtures.

Parallel edges combined with self-loops are a combination native kernels
frequently mishandle (degree must count a self-loop as 2 and tally every
parallel edge). This pins fnx == nx for MultiGraph and MultiDiGraph across
such fixtures.

br-r37-c1-du4a6
"""

from __future__ import annotations

import math

import pytest
import networkx as nx
import franken_networkx as fnx

_FIXTURES = {
    "parallel": [(0, 1), (0, 1), (1, 2)],
    "parallel_selfloop": [(0, 1), (0, 1), (0, 0), (1, 2)],
    "triple_parallel": [(0, 1), (0, 1), (0, 1)],
    "selfloop_only": [(0, 0), (1, 1)],
    "multi_complete": [(0, 1), (0, 1), (1, 2), (1, 2), (0, 2)],
}

_METRICS = [
    "number_of_edges", "number_of_selfloops", "degree_centrality",
    "number_connected_components", "density",
]

_CLASSES = [
    (fnx.MultiGraph, nx.MultiGraph, "MG"),
    (fnx.MultiDiGraph, nx.MultiDiGraph, "MDG"),
]


def _equal(f, x):
    if isinstance(f, float) and isinstance(x, float):
        return (math.isnan(f) and math.isnan(x)) or abs(f - x) <= 1e-9 * max(1, abs(x))
    if isinstance(f, dict) and isinstance(x, dict):
        return set(f) == set(x) and all(_equal(f[k], x[k]) for k in f)
    return f == x


@pytest.mark.parametrize("cls_index", [0, 1], ids=["MG", "MDG"])
@pytest.mark.parametrize("fixture", list(_FIXTURES))
@pytest.mark.parametrize("metric", _METRICS)
def test_multigraph_metric_matches_networkx(metric, fixture, cls_index):
    fnx_cls, nx_cls, _ = _CLASSES[cls_index]
    edges = _FIXTURES[fixture]
    fg = fnx_cls(edges)
    ng = nx_cls(edges)
    # number_connected_components is undirected-only; skip for directed.
    if metric == "number_connected_components" and fg.is_directed():
        pytest.skip("undirected-only metric")
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
        assert f_err is not None and x_err is not None
    else:
        assert _equal(f, x), f"{metric}[{fixture}]: {f!r} != {x!r}"


@pytest.mark.parametrize("cls_index", [0, 1], ids=["MG", "MDG"])
@pytest.mark.parametrize("fixture", list(_FIXTURES))
def test_multigraph_degree_counts_parallel_and_selfloops(fixture, cls_index):
    fnx_cls, nx_cls, _ = _CLASSES[cls_index]
    edges = _FIXTURES[fixture]
    assert dict(fnx_cls(edges).degree()) == dict(nx_cls(edges).degree())
