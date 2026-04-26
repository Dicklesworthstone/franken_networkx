"""Parity for ``isolates(G)`` return type.

Bead br-r37-c1-lby4x. fnx.isolates returned a ``list_iterator`` (the
Rust binding materializes the full list eagerly) while nx.isolates
returns a ``generator`` (lazy). Drop-in code doing
``isinstance(result, types.GeneratorType)`` failed on fnx; short-circuit
patterns like ``next(isolates(huge_graph))`` paid for full
materialisation on fnx vs. a single node-step on nx.
"""

from __future__ import annotations

import inspect
import types

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


@needs_nx
def test_isolates_returns_generator_like_networkx():
    G = fnx.Graph()
    G.add_nodes_from([0, 1, 2, 3])
    G.add_edge(0, 1)

    result = fnx.isolates(G)
    assert isinstance(result, types.GeneratorType)


@needs_nx
def test_isolates_values_match_networkx():
    G = fnx.Graph()
    G.add_nodes_from([0, 1, 2, 3, 4])
    G.add_edge(0, 1)
    G.add_edge(2, 3)

    nxg = nx.Graph()
    nxg.add_nodes_from([0, 1, 2, 3, 4])
    nxg.add_edge(0, 1)
    nxg.add_edge(2, 3)

    assert sorted(fnx.isolates(G)) == sorted(nx.isolates(nxg)) == [4]


@needs_nx
def test_isolates_lazy_iteration():
    """Calling next() on the generator must work."""
    G = fnx.Graph()
    G.add_nodes_from([10, 20, 30])
    # All three are isolates.
    it = fnx.isolates(G)
    first = next(it)
    rest = list(it)
    assert {first, *rest} == {10, 20, 30}


@needs_nx
def test_isolates_empty_graph():
    G = fnx.Graph()
    assert list(fnx.isolates(G)) == []


@needs_nx
def test_isolates_no_isolates_in_graph():
    """Path graph has no isolates."""
    G = fnx.path_graph(5)
    assert list(fnx.isolates(G)) == []


@needs_nx
def test_isolates_multigraph():
    MG = fnx.MultiGraph()
    MG.add_nodes_from(["a", "b", "c", "d"])
    MG.add_edge("a", "b")
    MG.add_edge("a", "b", key="parallel")
    nxmg = nx.MultiGraph()
    nxmg.add_nodes_from(["a", "b", "c", "d"])
    nxmg.add_edge("a", "b")
    nxmg.add_edge("a", "b", key="parallel")
    assert sorted(fnx.isolates(MG)) == sorted(nx.isolates(nxmg)) == ["c", "d"]


@needs_nx
def test_isolates_directed_graph_treats_isolation_correctly():
    """An isolate in a digraph is a node with both in- and out-degree 0."""
    G = fnx.DiGraph()
    G.add_nodes_from([0, 1, 2, 3])
    G.add_edge(0, 1)
    nxg = nx.DiGraph()
    nxg.add_nodes_from([0, 1, 2, 3])
    nxg.add_edge(0, 1)
    assert sorted(fnx.isolates(G)) == sorted(nx.isolates(nxg)) == [2, 3]


@needs_nx
def test_isolates_is_callable_with_kwargs_in_drop_in_code():
    """The wrapper accepts the documented ``G`` parameter; positional
    shape is preserved for backwards-compat."""
    G = fnx.Graph()
    G.add_nodes_from([0, 1])
    G.add_edge(0, 1)

    sig = inspect.signature(fnx.isolates)
    assert "G" in sig.parameters
    # Positional and kwarg both work.
    list(fnx.isolates(G))
    list(fnx.isolates(G=G))
