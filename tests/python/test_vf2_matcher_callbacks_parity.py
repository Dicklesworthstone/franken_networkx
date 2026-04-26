"""Parity for VF2 matcher node_match / edge_match constructors.

Bead br-r37-c1-matchersig. The ``_matcher_factory`` that builds
GraphMatcher / DiGraphMatcher / MultiGraphMatcher / MultiDiGraphMatcher
declared ``__init__(self, G1, G2)``, shadowing the node_match and
edge_match callback hooks nx exposes. Drop-in code calling
``GraphMatcher(G1, G2, node_match=fn)`` raised TypeError on fnx but
worked on nx.

Note: the inline classes earlier in __init__.py *did* have the right
signature, but the factory at the bottom overwrites them via module-
level reassignment. Fix: update the factory's ``__init__`` to accept
and forward both callbacks.
"""

from __future__ import annotations

import inspect

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


MATCHER_NAMES = [
    "GraphMatcher",
    "DiGraphMatcher",
    "MultiGraphMatcher",
    "MultiDiGraphMatcher",
]


@needs_nx
@pytest.mark.parametrize("name", MATCHER_NAMES)
def test_matcher_constructor_signature_matches_networkx(name):
    fnx_sig = inspect.signature(getattr(fnx, name))
    nx_sig = inspect.signature(getattr(nx.isomorphism, name))
    fnx_params = list(fnx_sig.parameters.keys())
    nx_params = list(nx_sig.parameters.keys())
    assert fnx_params == nx_params == ["G1", "G2", "node_match", "edge_match"]


@needs_nx
def test_graphmatcher_node_match_callback_invoked():
    """Pass a node_match callback that always returns False; the
    isomorphism check must reflect that constraint."""
    G1 = fnx.complete_graph(4)
    G2 = fnx.complete_graph(4)

    always_false = lambda d1, d2: False  # noqa: E731
    m = fnx.GraphMatcher(G1, G2, node_match=always_false)
    assert not m.is_isomorphic()

    always_true = lambda d1, d2: True  # noqa: E731
    m = fnx.GraphMatcher(G1, G2, node_match=always_true)
    assert m.is_isomorphic()


@needs_nx
def test_digraph_matcher_edge_match_callback_invoked():
    G1 = fnx.DiGraph()
    G1.add_edge(0, 1, color="red")
    G1.add_edge(1, 2, color="red")
    G2 = fnx.DiGraph()
    G2.add_edge(0, 1, color="red")
    G2.add_edge(1, 2, color="red")

    color_match = lambda d1, d2: d1.get("color") == d2.get("color")
    m = fnx.DiGraphMatcher(G1, G2, edge_match=color_match)
    assert m.is_isomorphic()

    G3 = fnx.DiGraph()
    G3.add_edge(0, 1, color="blue")
    G3.add_edge(1, 2, color="red")
    m = fnx.DiGraphMatcher(G1, G3, edge_match=color_match)
    # Mismatched colours → not isomorphic under the constraint
    assert not m.is_isomorphic()


@needs_nx
def test_multigraph_matcher_accepts_kwargs():
    """MultiGraphMatcher previously rejected the kwargs entirely
    (TypeError). Confirm both callbacks are accepted."""
    M = fnx.MultiGraph()
    M.add_edges_from([(0, 1), (1, 2)])
    m = fnx.MultiGraphMatcher(
        M, M,
        node_match=lambda d1, d2: True,
        edge_match=lambda d1, d2: True,
    )
    assert m.is_isomorphic()


@needs_nx
def test_multidigraph_matcher_accepts_kwargs():
    M = fnx.MultiDiGraph()
    M.add_edges_from([(0, 1), (1, 2)])
    m = fnx.MultiDiGraphMatcher(
        M, M,
        node_match=lambda d1, d2: True,
        edge_match=lambda d1, d2: True,
    )
    assert m.is_isomorphic()


@needs_nx
@pytest.mark.parametrize("name", MATCHER_NAMES)
def test_matcher_default_construction_still_works(name):
    """The 2-arg form must continue to work for existing callers."""
    cls = getattr(fnx, name)
    if name in ("DiGraphMatcher", "MultiDiGraphMatcher"):
        G = fnx.DiGraph() if "Multi" not in name else fnx.MultiDiGraph()
    else:
        G = fnx.Graph() if "Multi" not in name else fnx.MultiGraph()
    G.add_edges_from([(0, 1), (1, 2)])
    m = cls(G, G)
    assert m is not None
