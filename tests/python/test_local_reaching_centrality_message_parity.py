"""Parity for ``local_reaching_centrality`` missing-node wording.

networkx computes the reaching paths via ``shortest_path(G, v)``, whose
missing-source error is ``Source v not in G`` (no "is"). fnx's weight=None
perf path (br-r37-c1-lrcdist) routes through
``single_source_shortest_path_length``, which says "Source v is not in
G" — a wording regression. This locks fnx to nx's exact message.
br-r37-c1-ai5i9
"""

from __future__ import annotations

import pytest
import networkx as nx
import franken_networkx as fnx


@pytest.mark.parametrize(
    "fnx_cls,nx_cls", [(fnx.DiGraph, nx.DiGraph), (fnx.Graph, nx.Graph)],
    ids=["directed", "undirected"],
)
@pytest.mark.parametrize("missing", ["x", 99])
def test_local_reaching_centrality_missing_node_matches_networkx(
    fnx_cls, nx_cls, missing
):
    fg = fnx_cls([(0, 1), (1, 2)])
    ng = nx_cls([(0, 1), (1, 2)])
    with pytest.raises(nx.NodeNotFound) as fnx_exc:
        fnx.local_reaching_centrality(fg, missing)
    with pytest.raises(nx.NodeNotFound) as nx_exc:
        nx.local_reaching_centrality(ng, missing)
    assert str(fnx_exc.value) == str(nx_exc.value)


def test_message_has_no_is_and_no_quotes():
    fg = fnx.DiGraph([(0, 1), (1, 2)])
    with pytest.raises(nx.NodeNotFound) as exc:
        fnx.local_reaching_centrality(fg, "x")
    assert str(exc.value) == "Source x not in G"


def test_valid_local_reaching_centrality_unaffected():
    fg = fnx.DiGraph([(0, 1), (1, 2)])
    ng = nx.DiGraph([(0, 1), (1, 2)])
    assert fnx.local_reaching_centrality(fg, 0) == pytest.approx(
        nx.local_reaching_centrality(ng, 0)
    )
