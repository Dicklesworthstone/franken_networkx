"""Parity for ``random_clustered_graph`` positional argument order.

Self-review found that fnx had ``(joint_degree_sequence, seed, create_using)``
while networkx has ``(joint_degree_sequence, create_using, seed)``. A
positional call like::

    fnx.random_clustered_graph(seq, MultiGraph, 42)

was interpreted on fnx as ``seed=MultiGraph, create_using=42`` and
crashed with ``"create_using is not a valid NetworkX graph type"``,
while the same call worked on nx. Aligned the order.
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


@needs_nx
def test_random_clustered_graph_positional_order_matches_networkx():
    fnx_sig = inspect.signature(fnx.random_clustered_graph)
    nx_sig = inspect.signature(nx.random_clustered_graph)
    fnx_pos = [k for k, v in fnx_sig.parameters.items()
               if v.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD]
    nx_pos = [k for k, v in nx_sig.parameters.items()
              if v.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD]
    assert fnx_pos == nx_pos == ["joint_degree_sequence", "create_using", "seed"]


@needs_nx
def test_random_clustered_graph_positional_call_matches_networkx():
    """Positional call (seq, create_using, seed) must work identically."""
    seq = [(2, 0), (2, 0), (2, 0), (2, 0)]
    fnx_g = fnx.random_clustered_graph(seq, fnx.MultiGraph, 42)
    nx_g = nx.random_clustered_graph(seq, nx.MultiGraph, 42)
    assert fnx_g.number_of_nodes() == nx_g.number_of_nodes()
    assert fnx_g.number_of_edges() == nx_g.number_of_edges()
    assert fnx_g.is_multigraph()
    assert nx_g.is_multigraph()


@needs_nx
def test_random_clustered_graph_kwarg_call_matches_networkx():
    seq = [(1, 0), (1, 0), (1, 0), (1, 0)]
    fnx_g = fnx.random_clustered_graph(seq, seed=42)
    nx_g = nx.random_clustered_graph(seq, seed=42)
    assert fnx_g.number_of_nodes() == nx_g.number_of_nodes()
    assert fnx_g.number_of_edges() == nx_g.number_of_edges()


@needs_nx
def test_random_clustered_graph_positional_create_using_is_class_not_seed():
    """The bug was that fnx interpreted positional arg #2 as seed; if
    that bug were still present, passing fnx.MultiGraph (a class) as
    arg #2 would fail with 'cannot use class as seed' or similar.
    Confirm a positional-class call works."""
    seq = [(2, 0)] * 4
    g = fnx.random_clustered_graph(seq, fnx.MultiGraph, 7)
    assert g.is_multigraph()
    assert not g.is_directed()
