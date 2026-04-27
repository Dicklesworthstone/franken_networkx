"""Parity for ``Graph.edges(nbunch)`` when the nbunch sequence
contains unhashable elements.

Bead br-r37-c1-w5sa7.

Pre-fix only the undirected ``Graph`` path leaked the bare Rust
``TypeError("unhashable type: 'list'")`` because
``EdgeDataView.__init__`` did ``self._nbset = set(nbunch_list)``
unguarded.  ``DiGraph`` / ``MultiGraph`` / ``MultiDiGraph`` /
``nbunch_iter`` all already matched nx's
``NetworkXError("Node [1, 2] in sequence nbunch is not a valid
node.")`` — so this is a single-class drift, not a systemic
binding-level issue.
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

UNHASHABLE = [
    pytest.param([1, 2], id="list"),
    pytest.param({1, 2}, id="set"),
    pytest.param({"a": 1}, id="dict"),
]


@needs_nx
@pytest.mark.parametrize("val", UNHASHABLE)
def test_graph_edges_nbunch_unhashable_raises_networkxerror(val):
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    with pytest.raises(fnx.NetworkXError, match=r"in sequence nbunch is not a valid node"):
        list(G.edges([val]))
    with pytest.raises(nx.NetworkXError, match=r"in sequence nbunch is not a valid node"):
        list(GX.edges([val]))


@needs_nx
@pytest.mark.parametrize("val", UNHASHABLE)
def test_graph_edges_nbunch_mixed_unhashable_raises_networkxerror(val):
    """A mixed list of valid + unhashable triggers nx's same error
    on the first unhashable element encountered."""
    G = fnx.Graph([(1, 2), (2, 3)])
    GX = nx.Graph([(1, 2), (2, 3)])
    with pytest.raises(fnx.NetworkXError, match=r"in sequence nbunch is not a valid node"):
        list(G.edges([1, val]))
    with pytest.raises(nx.NetworkXError, match=r"in sequence nbunch is not a valid node"):
        list(GX.edges([1, val]))


# ---------------------------------------------------------------------------
# Sister classes already matched — guard to keep them green
# ---------------------------------------------------------------------------

@needs_nx
def test_digraph_edges_nbunch_unhashable_unchanged():
    DG = fnx.DiGraph([(1, 2)])
    DGX = nx.DiGraph([(1, 2)])
    with pytest.raises(fnx.NetworkXError, match=r"in sequence nbunch is not a valid node"):
        list(DG.edges([[1, 2]]))
    with pytest.raises(nx.NetworkXError, match=r"in sequence nbunch is not a valid node"):
        list(DGX.edges([[1, 2]]))


@needs_nx
def test_multigraph_edges_nbunch_unhashable_unchanged():
    MG = fnx.MultiGraph([(1, 2)])
    MGX = nx.MultiGraph([(1, 2)])
    with pytest.raises(fnx.NetworkXError, match=r"in sequence nbunch is not a valid node"):
        list(MG.edges([[1, 2]]))
    with pytest.raises(nx.NetworkXError, match=r"in sequence nbunch is not a valid node"):
        list(MGX.edges([[1, 2]]))


# ---------------------------------------------------------------------------
# Regressions — hashable nbunch (valid + missing) unaffected
# ---------------------------------------------------------------------------

@needs_nx
def test_graph_edges_nbunch_hashable_unchanged():
    G = fnx.Graph([(1, 2), (2, 3), (3, 4)])
    GX = nx.Graph([(1, 2), (2, 3), (3, 4)])
    assert sorted(G.edges([1, 2])) == sorted(GX.edges([1, 2]))


@needs_nx
def test_graph_edges_nbunch_missing_silently_skipped():
    """nx silently skips missing-but-hashable nbunch members.
    Make sure my fix didn't accidentally start raising for them."""
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    assert list(G.edges([99])) == list(GX.edges([99])) == []


@needs_nx
def test_graph_edges_scalar_node_nbunch_unchanged():
    """Single-node (not iterable) nbunch still works — the
    ``[nbunch]`` fallback for non-iterables is unchanged."""
    G = fnx.Graph([(1, 2), (2, 3)])
    GX = nx.Graph([(1, 2), (2, 3)])
    assert sorted(G.edges(1)) == sorted(GX.edges(1))


@needs_nx
def test_graph_edges_with_data_and_nbunch_unchanged():
    """Combine nbunch with data=True — both kwargs path through
    EdgeDataView; nbset construction must not re-trigger."""
    G = fnx.Graph([(1, 2, {"w": 1}), (2, 3, {"w": 2})])
    GX = nx.Graph([(1, 2, {"w": 1}), (2, 3, {"w": 2})])
    f = sorted([(u, v, dict(d)) for u, v, d in G.edges([1, 2], data=True)], key=str)
    n = sorted([(u, v, dict(d)) for u, v, d in GX.edges([1, 2], data=True)], key=str)
    assert f == n
