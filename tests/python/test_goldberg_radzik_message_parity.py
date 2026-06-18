"""Parity for ``goldberg_radzik`` missing-source error wording.

networkx validates the source at the top of ``goldberg_radzik`` with
``NodeNotFound("Node {source} is not found in the graph")``. fnx
previously surfaced the internal bellman-ford wording
``Source x not in G``. This locks fnx to nx's exact message across
directed and undirected graphs. br-r37-c1-tnzt9
"""

from __future__ import annotations

import pytest
import networkx as nx
import franken_networkx as fnx


@pytest.mark.parametrize(
    "fnx_cls,nx_cls", [(fnx.Graph, nx.Graph), (fnx.DiGraph, nx.DiGraph)],
    ids=["undirected", "directed"],
)
@pytest.mark.parametrize("missing", ["x", 99])
def test_goldberg_radzik_missing_source_matches_networkx(fnx_cls, nx_cls, missing):
    fg = fnx_cls([(0, 1), (1, 2)])
    ng = nx_cls([(0, 1), (1, 2)])
    with pytest.raises(nx.NodeNotFound) as fnx_exc:
        fnx.goldberg_radzik(fg, missing)
    with pytest.raises(nx.NodeNotFound) as nx_exc:
        nx.goldberg_radzik(ng, missing)
    assert str(fnx_exc.value) == str(nx_exc.value)


def test_goldberg_radzik_message_exact_wording():
    fg = fnx.DiGraph([(0, 1), (1, 2)])
    with pytest.raises(nx.NodeNotFound) as exc:
        fnx.goldberg_radzik(fg, "x")
    assert str(exc.value) == "Node x is not found in the graph"


def test_goldberg_radzik_valid_query_unaffected():
    fg = fnx.DiGraph([(0, 1), (1, 2)])
    ng = nx.DiGraph([(0, 1), (1, 2)])
    assert fnx.goldberg_radzik(fg, 0) == nx.goldberg_radzik(ng, 0)
