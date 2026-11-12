"""Directed API-health parity: DiGraph-specific functions run and agree with nx.

A blind sweep of all callables on a DiGraph confirmed no fnx directed function
errors where networkx succeeds (the apparent hits were wrong-input-type or
generator-laziness artifacts). This curated subset pins the health of the
directed-specific surface on a proper DiGraph.

No mocks: real fnx and real networkx on a fresh standard DiGraph per call.
"""

from __future__ import annotations

import pytest
import networkx as nx
import franken_networkx as fnx


def _digraph(lib):
    g = lib.DiGraph()
    for u, v in [(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 2), (0, 3)]:
        g.add_edge(u, v, weight=1, capacity=2)
    return g


_FUNCS = [
    ("is_directed_acyclic_graph", bool),
    ("is_strongly_connected", bool),
    ("is_weakly_connected", bool),
    ("is_semiconnected", bool),
    ("is_aperiodic", bool),
    ("number_strongly_connected_components", int),
    ("number_weakly_connected_components", int),
    ("number_attracting_components", int),
    ("overall_reciprocity", float),
    ("transitivity", float),
    ("density", float),
    ("flow_hierarchy", float),
    ("is_eulerian", bool),
]


@pytest.mark.parametrize("name,norm", _FUNCS)
def test_directed_function_runs_and_matches(name, norm):
    ff = getattr(fnx, name, None)
    nf = getattr(nx, name, None)
    if ff is None or nf is None:
        pytest.skip(f"{name} not available")

    def outcome(fn, g):
        try:
            return ("ok", fn(g))
        except Exception as exc:  # noqa: BLE001
            return ("err", type(exc).__name__)

    f_kind, f_val = outcome(ff, _digraph(fnx))
    n_kind, n_val = outcome(nf, _digraph(nx))
    assert f_kind == n_kind, f"{name}: fnx={f_kind} nx={n_kind}"
    if f_kind == "ok":
        if norm is float:
            assert norm(f_val) == pytest.approx(norm(n_val))
        else:
            assert norm(f_val) == norm(n_val)


def test_directed_acyclic_helpers_on_a_dag():
    # On a proper DAG, ordering/ancestry helpers run and agree.
    fd = fnx.DiGraph([(0, 1), (0, 2), (1, 3), (2, 3), (3, 4)])
    nd = nx.DiGraph([(0, 1), (0, 2), (1, 3), (2, 3), (3, 4)])
    assert fnx.is_directed_acyclic_graph(fd)
    assert list(fnx.topological_sort(fd)) == list(nx.topological_sort(nd))
    assert fnx.dag_longest_path_length(fd) == nx.dag_longest_path_length(nd)
    for node in fd.nodes():
        assert fnx.ancestors(fd, node) == nx.ancestors(nd, node)
        assert fnx.descendants(fd, node) == nx.descendants(nd, node)
