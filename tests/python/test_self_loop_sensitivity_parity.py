"""Self-loop sensitivity parity net.

Self-loops are a recurring divergence source — the first bug in this series was
``degree(weight=)`` counting a self-loop's weight once instead of twice
(br-r37-c1-vuv97). networkx has two opposite contracts here:

  * degree / size / weighted degree / adjacency-matrix diagonal / pagerank
    are *affected* by self-loops (a self-loop adds 2 to undirected degree,
    its weight twice, etc.), and
  * clustering / triangles / transitivity / square_clustering *ignore*
    self-loops entirely.

This net pins both: for each function it asserts parity with networkx on a
graph with self-loops, AND that the value relates to the no-self-loop version
the right way (changed for the first group, identical for the second). A kernel
that mishandled self-loops in either direction would trip it.
"""

import math

import networkx as nx
import franken_networkx as fnx

import pytest


_BASE = [(0, 1), (1, 2), (2, 3), (3, 0), (0, 2), (2, 4)]
_LOOPS = [(2, 2), (4, 4)]


def _graph(mod, loops, weighted=False):
    g = mod.Graph()
    for i, (u, v) in enumerate(_BASE + (loops or [])):
        if weighted:
            g.add_edge(u, v, weight=float((i % 3) + 1))
        else:
            g.add_edge(u, v)
    return g


def _norm(x):
    if isinstance(x, dict):
        return {k: _norm(v) for k, v in x.items()}
    if isinstance(x, float):
        return round(x, 9) if math.isfinite(x) else repr(x)
    return x


def _eq(a, b, tol=1e-9):
    if isinstance(a, dict):
        return set(a) == set(b) and all(_eq(a[k], b[k], tol) for k in a)
    if isinstance(a, float):
        return abs(a - b) <= tol
    return a == b


# (label, call) -> functions whose result IS affected by self-loops.
_AFFECTED = {
    "degree": lambda m, g: dict(g.degree()),
    "degree_weighted": lambda m, g: dict(g.degree(weight="weight")),
    "size": lambda m, g: g.size(),
    "size_weighted": lambda m, g: g.size(weight="weight"),
    "number_of_selfloops": lambda m, g: m.number_of_selfloops(g),
    "pagerank": lambda m, g: m.pagerank(g),
    "degree_centrality": lambda m, g: m.degree_centrality(g),
}

# functions where networkx ignores self-loops (result == no-self-loop result).
_IGNORES = {
    "clustering": lambda m, g: m.clustering(g),
    "triangles": lambda m, g: m.triangles(g),
    "transitivity": lambda m, g: round(m.transitivity(g), 9),
    "square_clustering": lambda m, g: m.square_clustering(g),
    "average_clustering": lambda m, g: round(m.average_clustering(g), 9),
}


@pytest.mark.parametrize("label", sorted(_AFFECTED))
def test_affected_function_matches_networkx(label):
    fn = _AFFECTED[label]
    weighted = "weighted" in label
    gn, gf = _graph(nx, _LOOPS, weighted), _graph(fnx, _LOOPS, weighted)
    assert _eq(_norm(fn(nx, gn)), _norm(fn(fnx, gf))), label


@pytest.mark.parametrize("label", sorted(_AFFECTED))
def test_affected_function_changes_with_self_loops(label):
    # Non-vacuity: the self-loops must change the result vs the loop-free graph,
    # or the test couldn't catch a "self-loop dropped" regression.
    if label == "number_of_selfloops":
        pytest.skip("trivially 2 vs 0 — covered by parity test")
    fn = _AFFECTED[label]
    weighted = "weighted" in label
    with_loops = _norm(fn(fnx, _graph(fnx, _LOOPS, weighted)))
    no_loops = _norm(fn(fnx, _graph(fnx, [], weighted)))
    assert not _eq(with_loops, no_loops), f"{label}: self-loops did not change the result"


@pytest.mark.parametrize("label", sorted(_IGNORES))
def test_ignoring_function_matches_networkx_and_ignores_self_loops(label):
    fn = _IGNORES[label]
    gn, gf = _graph(nx, _LOOPS), _graph(fnx, _LOOPS)
    # parity with nx on the self-loop graph
    assert _eq(_norm(fn(nx, gn)), _norm(fn(fnx, gf))), f"{label}: fnx != nx"
    # and fnx ignores self-loops exactly like nx (== loop-free result)
    assert _eq(_norm(fn(fnx, gf)), _norm(fn(fnx, _graph(fnx, [])))), (
        f"{label}: fnx does not ignore self-loops the way nx does"
    )


def test_self_loop_weighted_degree_double_counts():
    # Direct guard for the original bug (vuv97): a self-loop's weight counts
    # twice in undirected weighted degree.
    gn = nx.Graph(); gn.add_edge(0, 1, weight=4.0); gn.add_edge(1, 1, weight=5.0)
    gf = fnx.Graph(); gf.add_edge(0, 1, weight=4.0); gf.add_edge(1, 1, weight=5.0)
    assert fnx.Graph(gf).degree(1, weight="weight") == gn.degree(1, weight="weight") == 14.0
