"""Differential parity for directed metrics on degenerate digraphs.

Same high-risk input class that surfaced the node_connectivity P1 bugs,
applied to directed graphs: 2-cycles, self-loops, pure sources/sinks,
in/out stars. ``hits`` is intentionally excluded — it is mathematically
ill-conditioned on these tiny degenerate graphs (its principal eigenvector
is not well separated, so *both* fnx and nx return sign-ambiguous /
negative scores); fnx matches nx 0/35 on strongly connected digraphs where
HITS is well defined.

br-r37-c1-1pgkz
"""

from __future__ import annotations

import math

import pytest
import networkx as nx
import franken_networkx as fnx

_FIXTURES = {
    "two_cycle": ([(0, 1), (1, 0)], []),
    "self_loop": ([(0, 1), (1, 2), (0, 0)], []),
    "source_sink": ([(0, 1), (0, 2), (1, 3), (2, 3)], []),
    "star_out": ([(0, 1), (0, 2), (0, 3)], []),
    "star_in": ([(1, 0), (2, 0), (3, 0)], []),
    "complete_di": ([(0, 1), (1, 0), (0, 2), (2, 0), (1, 2), (2, 1)], []),
    "chain": ([(0, 1), (1, 2), (2, 3)], []),
    "isolated": ([(0, 1)], [9]),
}

_METRICS = [
    "in_degree_centrality", "out_degree_centrality", "pagerank",
    "reciprocity", "overall_reciprocity",
    "number_strongly_connected_components", "number_weakly_connected_components",
    "transitivity", "number_of_selfloops",
]


def _build(lib, edges, extra):
    g = lib.DiGraph(edges)
    g.add_nodes_from(extra)
    return g


def _equal(f, x):
    if isinstance(f, float) and isinstance(x, float):
        return (math.isnan(f) and math.isnan(x)) or abs(f - x) <= 1e-9 * max(1, abs(x))
    if isinstance(f, dict) and isinstance(x, dict):
        return set(f) == set(x) and all(_equal(f[k], x[k]) for k in f)
    return f == x


@pytest.mark.parametrize("fixture", list(_FIXTURES))
@pytest.mark.parametrize("metric", _METRICS)
def test_directed_metric_matches_networkx_on_degenerate_digraph(metric, fixture):
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
        assert f_err is not None and x_err is not None, (
            f"{metric}[{fixture}] raise mismatch: {f_err} vs {x_err}"
        )
    else:
        assert _equal(f, x), f"{metric}[{fixture}]: {f!r} != {x!r}"


# br-r37-c1-2fx0w: nx answers {n: 1} for a graph of at most one node; fnx's
# multigraph branch answered 0 there. Parallel edges count in the degrees.
@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("n", [0, 1, 2, 4])
@pytest.mark.parametrize("metric", ["in_degree_centrality", "out_degree_centrality", "degree_centrality"])
def test_degree_centrality_small_directed_graphs_match_networkx(cls, n, metric):
    def outcome(lib):
        g = getattr(lib, cls)()
        g.add_nodes_from(range(n))
        if n >= 2:
            g.add_edges_from([(0, 1), (0, 1), (1, 0)])
        return [(k, repr(v), type(v).__name__) for k, v in getattr(lib, metric)(g).items()]

    assert outcome(fnx) == outcome(nx)
