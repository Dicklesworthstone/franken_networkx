"""Parity for ``Graph.__eq__`` / ``Graph.__hash__`` semantics.

Bead br-r37-c1-xsrkr. fnx.Graph defined content-based ``__eq__`` in
the Rust binding. Drop-in consequences:

- ``fnx.path_graph(3) == fnx.path_graph(3)`` returned True; nx returns
  False (identity-based comparison).
- Python automatically set ``__hash__ = None`` because ``__eq__`` was
  overridden, making instances unhashable. ``set([G1, G2])`` raised
  TypeError on fnx but worked on nx.

Fix overrides ``__eq__`` and ``__hash__`` on all four Graph classes to
use ``object``'s defaults (identity-based) matching nx's drop-in
semantics exactly.
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


CLASSES = (
    (fnx.Graph, nx.Graph) if HAS_NX else (None, None),
    (fnx.DiGraph, nx.DiGraph) if HAS_NX else (None, None),
    (fnx.MultiGraph, nx.MultiGraph) if HAS_NX else (None, None),
    (fnx.MultiDiGraph, nx.MultiDiGraph) if HAS_NX else (None, None),
)
CLASS_IDS = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


@needs_nx
@pytest.mark.parametrize("fnx_cls,nx_cls", CLASSES, ids=CLASS_IDS)
def test_two_distinct_graphs_with_same_content_are_unequal(fnx_cls, nx_cls):
    """nx uses identity-equality. Two distinct instances with same
    content are NOT equal — fnx must match."""
    f1 = fnx_cls(); f2 = fnx_cls()
    f1.add_edge(0, 1)
    f2.add_edge(0, 1)
    assert f1 != f2
    # Sanity: nx does the same.
    n1 = nx_cls(); n2 = nx_cls()
    n1.add_edge(0, 1)
    n2.add_edge(0, 1)
    assert n1 != n2


@needs_nx
@pytest.mark.parametrize("fnx_cls,nx_cls", CLASSES, ids=CLASS_IDS)
def test_same_object_is_equal_to_itself(fnx_cls, nx_cls):
    g = fnx_cls()
    g.add_edge(0, 1)
    assert g == g
    n = nx_cls()
    n.add_edge(0, 1)
    assert n == n


@needs_nx
@pytest.mark.parametrize("fnx_cls,nx_cls", CLASSES, ids=CLASS_IDS)
def test_graph_is_hashable(fnx_cls, nx_cls):
    g = fnx_cls()
    g.add_edge(0, 1)
    # Must not raise — __hash__ is identity-based per nx contract.
    h = hash(g)
    assert isinstance(h, int)


@needs_nx
@pytest.mark.parametrize("fnx_cls,nx_cls", CLASSES, ids=CLASS_IDS)
def test_distinct_graphs_have_distinct_hashes(fnx_cls, nx_cls):
    """Identity-based hash means each instance has its own hash."""
    g1 = fnx_cls(); g2 = fnx_cls()
    assert hash(g1) != hash(g2)


@needs_nx
@pytest.mark.parametrize("fnx_cls,nx_cls", CLASSES, ids=CLASS_IDS)
def test_set_with_two_distinct_graphs_has_size_two(fnx_cls, nx_cls):
    """``set([g1, g2])`` must work — both fnx and nx support it."""
    g1 = fnx_cls(); g2 = fnx_cls()
    s = set([g1, g2])
    assert len(s) == 2


@needs_nx
@pytest.mark.parametrize("fnx_cls,nx_cls", CLASSES, ids=CLASS_IDS)
def test_dict_keyed_by_graph_works(fnx_cls, nx_cls):
    """Drop-in code that uses graphs as dict keys must work."""
    g1 = fnx_cls(); g2 = fnx_cls()
    cache = {g1: "first", g2: "second"}
    assert cache[g1] == "first"
    assert cache[g2] == "second"


@needs_nx
@pytest.mark.parametrize("fnx_cls,nx_cls", CLASSES, ids=CLASS_IDS)
def test_set_with_same_graph_twice_has_size_one(fnx_cls, nx_cls):
    """A graph in a set twice (same instance) deduplicates to one."""
    g = fnx_cls()
    s = set([g, g])
    assert len(s) == 1


@needs_nx
def test_graph_neq_to_non_graph_returns_false_not_typeerror():
    """``g == 'not a graph'`` should return False, not raise."""
    g = fnx.Graph()
    assert (g == "not a graph") is False
    assert (g == 42) is False
    assert (g == None) is False  # noqa: E711
