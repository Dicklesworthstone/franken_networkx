"""Parity for node_link_data / node_link_graph keyword-only overrides.

Self-review found that fnx.node_link_data and fnx.node_link_graph
accepted ``source`` / ``target`` / etc. as positional arguments while
networkx requires them keyword-only. Reproducer:

    fnx.node_link_data(G, "from_", "to_")  # worked on fnx, raised on nx

Hardened the signatures with ``*,`` so positional usage is rejected
identically. These tests freeze that contract.
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
def test_node_link_data_rejects_positional_source_target():
    """nx requires source/target as keyword-only; fnx must agree."""
    G = fnx.karate_club_graph()
    with pytest.raises(TypeError):
        fnx.node_link_data(G, "from_", "to_")


@needs_nx
def test_node_link_data_kwarg_renames_match_networkx():
    G = fnx.karate_club_graph()
    GX = nx.karate_club_graph()
    actual = fnx.node_link_data(G, source="src", target="dst")
    expected = nx.node_link_data(GX, source="src", target="dst")
    assert sorted(actual.keys()) == sorted(expected.keys())
    # The rename should appear in every edge dict
    assert all("src" in e and "dst" in e for e in actual["edges"])
    assert all("src" in e and "dst" in e for e in expected["edges"])
    assert len(actual["edges"]) == len(expected["edges"])


@needs_nx
def test_node_link_graph_rejects_positional_source_target():
    """nx accepts directed/multigraph as positional but field-name
    overrides are keyword-only. fnx must agree."""
    G = fnx.karate_club_graph()
    data = fnx.node_link_data(G)
    with pytest.raises(TypeError):
        # 4th positional would be the old fnx 'source' arg
        fnx.node_link_graph(data, False, False, "src")


@needs_nx
def test_node_link_roundtrip_with_renamed_fields():
    G = fnx.karate_club_graph()
    GX = nx.karate_club_graph()
    data = fnx.node_link_data(G, source="src", target="dst")
    rebuilt = fnx.node_link_graph(data, source="src", target="dst")
    rebuilt_nx = nx.node_link_graph(
        nx.node_link_data(GX, source="src", target="dst"),
        source="src",
        target="dst",
    )
    assert sorted(rebuilt.edges()) == sorted(rebuilt_nx.edges())


@needs_nx
def test_node_link_graph_default_kwargs_match_networkx():
    """Defaults still go through cleanly — the kwarg-only constraint
    only blocks positional use, not the default path."""
    G = fnx.karate_club_graph()
    GX = nx.karate_club_graph()
    rebuilt = fnx.node_link_graph(fnx.node_link_data(G))
    rebuilt_nx = nx.node_link_graph(nx.node_link_data(GX))
    assert sorted(rebuilt.edges()) == sorted(rebuilt_nx.edges())
