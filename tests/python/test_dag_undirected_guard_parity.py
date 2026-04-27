"""Parity for DAG-only algorithms when given undirected input.

Bead br-r37-c1-6nhsw. Two parity defects on undirected inputs:

(1) ``lexicographical_topological_sort`` silently succeeded on
    undirected graphs; nx raises NetworkXError. The plain
    ``topological_sort`` already raised correctly.

(2) ``dag_to_branching`` raised ``HasACycle`` on undirected input;
    nx raises ``NetworkXNotImplemented`` first via the
    ``@not_implemented_for('undirected')`` decorator. ``HasACycle``
    is NOT a subclass of ``NetworkXNotImplemented`` so drop-in
    code that does ``except NetworkXNotImplemented`` would not
    catch fnx's exception.
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


# ---------------------------------------------------------------------------
# lexicographical_topological_sort: undirected input → NetworkXError
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize(
    "graph_factory_name", ["Graph", "MultiGraph"]
)
def test_lex_topo_sort_rejects_undirected(graph_factory_name):
    G = getattr(fnx, graph_factory_name)([(1, 2), (2, 3)])
    GX = getattr(nx, graph_factory_name)([(1, 2), (2, 3)])
    with pytest.raises(
        fnx.NetworkXError,
        match=r"Topological sort not defined on undirected graphs\.",
    ):
        list(fnx.lexicographical_topological_sort(G))
    with pytest.raises(
        nx.NetworkXError,
        match=r"Topological sort not defined on undirected graphs\.",
    ):
        list(nx.lexicographical_topological_sort(GX))


@needs_nx
def test_lex_topo_sort_dag_unchanged():
    """Regression guard — DAG inputs continue to yield the
    lexicographic order (matches nx)."""
    G = fnx.DiGraph([(0, 1), (0, 2), (1, 3), (2, 3)])
    GX = nx.DiGraph([(0, 1), (0, 2), (1, 3), (2, 3)])
    f = list(fnx.lexicographical_topological_sort(G))
    n = list(nx.lexicographical_topological_sort(GX))
    assert f == n


@needs_nx
def test_lex_topo_sort_cyclic_still_raises_unfeasible():
    """Pre-existing parity (unchanged): cyclic DG still raises
    NetworkXUnfeasible, not NetworkXError."""
    G = fnx.DiGraph([(1, 2), (2, 1)])
    GX = nx.DiGraph([(1, 2), (2, 1)])
    with pytest.raises(fnx.NetworkXUnfeasible):
        list(fnx.lexicographical_topological_sort(G))
    with pytest.raises(nx.NetworkXUnfeasible):
        list(nx.lexicographical_topological_sort(GX))


# ---------------------------------------------------------------------------
# dag_to_branching: undirected input → NetworkXNotImplemented
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize(
    "graph_factory_name", ["Graph", "MultiGraph"]
)
def test_dag_to_branching_rejects_undirected(graph_factory_name):
    G = getattr(fnx, graph_factory_name)([(1, 2)])
    GX = getattr(nx, graph_factory_name)([(1, 2)])
    with pytest.raises(
        fnx.NetworkXNotImplemented,
        match=r"not implemented for undirected type",
    ):
        fnx.dag_to_branching(G)
    with pytest.raises(
        nx.NetworkXNotImplemented,
        match=r"not implemented for undirected type",
    ):
        nx.dag_to_branching(GX)


@needs_nx
def test_dag_to_branching_undirected_caught_by_nx_class():
    """Drop-in: pre-fix fnx raised HasACycle which is NOT a subclass
    of nx.NetworkXNotImplemented, so ``except NetworkXNotImplemented``
    silently failed under fnx."""
    G = fnx.Graph([(1, 2)])
    try:
        fnx.dag_to_branching(G)
    except nx.NetworkXNotImplemented:
        return
    pytest.fail(
        "fnx.dag_to_branching should raise NetworkXNotImplemented on "
        "undirected input"
    )


@needs_nx
def test_dag_to_branching_cyclic_directed_still_raises_has_a_cycle():
    """Pre-existing parity (unchanged): a cyclic DiGraph still
    raises HasACycle. Only the undirected case was misrouted."""
    G = fnx.DiGraph([(1, 2), (2, 1)])
    GX = nx.DiGraph([(1, 2), (2, 1)])
    with pytest.raises(fnx.HasACycle):
        fnx.dag_to_branching(G)
    with pytest.raises(nx.HasACycle):
        nx.dag_to_branching(GX)


@needs_nx
def test_dag_to_branching_dag_unchanged():
    """Regression guard — DAG happy path matches nx."""
    G = fnx.DiGraph([(0, 1), (0, 2), (1, 3), (2, 3)])
    GX = nx.DiGraph([(0, 1), (0, 2), (1, 3), (2, 3)])
    f = sorted(fnx.dag_to_branching(G).edges())
    n = sorted(nx.dag_to_branching(GX).edges())
    assert f == n


# ---------------------------------------------------------------------------
# br-r37-c1-06ubx: dag_to_branching also rejects multigraph input
# ---------------------------------------------------------------------------

@needs_nx
def test_dag_to_branching_rejects_multidigraph():
    """nx is decorated with @not_implemented_for('multigraph') in
    addition to @not_implemented_for('undirected'). MultiDiGraph
    (directed + multigraph) must raise 'not implemented for
    multigraph type' on both libraries."""
    G = fnx.MultiDiGraph([(1, 2), (2, 3)])
    GX = nx.MultiDiGraph([(1, 2), (2, 3)])
    with pytest.raises(
        fnx.NetworkXNotImplemented,
        match=r"not implemented for multigraph type",
    ):
        fnx.dag_to_branching(G)
    with pytest.raises(
        nx.NetworkXNotImplemented,
        match=r"not implemented for multigraph type",
    ):
        nx.dag_to_branching(GX)


@needs_nx
def test_dag_to_branching_multigraph_undirected_undirected_message_wins():
    """For MultiGraph (both undirected AND multigraph), nx's
    decorator stack runs the inner @not_implemented_for('undirected')
    check first, so 'undirected' wins. fnx must match that exact
    ordering — drop-in code that does
    ``pytest.raises(..., match='undirected')`` on MultiGraph would
    otherwise fail."""
    G = fnx.MultiGraph([(1, 2)])
    GX = nx.MultiGraph([(1, 2)])
    with pytest.raises(
        fnx.NetworkXNotImplemented,
        match=r"^not implemented for undirected type$",
    ):
        fnx.dag_to_branching(G)
    with pytest.raises(
        nx.NetworkXNotImplemented,
        match=r"^not implemented for undirected type$",
    ):
        nx.dag_to_branching(GX)
