"""br-r37-c1-ecua7: namespace parity — ``fnx.modularity`` must raise
``AttributeError`` so the namespace contract mirrors nx, which exposes
``modularity`` only under ``nx.community.modularity`` (and
``nx.algorithms.community.modularity``).

Same family as br-r37-c1-bw-removed (branching_weight, minimal_branching).
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


@needs_nx
def test_top_level_modularity_raises_attributeerror():
    """fnx must mirror nx's contract: top-level ``modularity`` is not
    a public attribute."""
    with pytest.raises(AttributeError, match=r"has no attribute 'modularity'"):
        fnx.modularity
    with pytest.raises(AttributeError, match=r"has no attribute 'modularity'"):
        nx.modularity


@needs_nx
def test_community_modularity_works():
    """The namespaced version still works (it dispatches through
    fnx's backend back to the private implementation)."""
    g = fnx.path_graph(10)
    result = fnx.community.modularity(g, [{0, 1, 2, 3, 4}, {5, 6, 7, 8, 9}])
    # Same computation through nx route
    ng = nx.path_graph(10)
    nx_result = nx.community.modularity(ng, [{0, 1, 2, 3, 4}, {5, 6, 7, 8, 9}])
    assert round(result, 6) == round(nx_result, 6)


@needs_nx
def test_algorithms_community_modularity_works():
    """The longer namespaced version also works."""
    g = fnx.path_graph(10)
    result = fnx.algorithms.community.modularity(
        g, [{0, 1, 2, 3, 4}, {5, 6, 7, 8, 9}]
    )
    assert isinstance(result, float)


@needs_nx
def test_backend_registers_modularity_via_private_impl():
    """The dispatcher must still be able to find a callable named
    'modularity' so ``nx.community.modularity(fnx_graph)`` works."""
    from franken_networkx.backend import _SUPPORTED_ALGORITHMS

    assert "modularity" in _SUPPORTED_ALGORITHMS
    assert _SUPPORTED_ALGORITHMS["modularity"] is fnx._modularity_backend_impl


@needs_nx
def test_modularity_via_nx_dispatch_on_fnx_graph():
    """``nx.community.modularity(fnx_graph, ...)`` dispatches through
    fnx's backend interface to the private implementation."""
    g = fnx.path_graph(10)
    result = nx.community.modularity(g, [{0, 1, 2, 3, 4}, {5, 6, 7, 8, 9}])
    assert isinstance(result, float)
