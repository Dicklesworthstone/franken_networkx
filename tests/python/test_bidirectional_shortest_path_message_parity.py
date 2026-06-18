"""Golden parity for ``bidirectional_shortest_path`` NodeNotFound wording.

The native binding leaked a repr-quoted ``Source 'x' is not in G`` for
absent nodes; networkx emits the unquoted ``Source x is not in G``
(source checked first, then target). br-r37-c1-qmu8x
"""

from __future__ import annotations

import pytest
import networkx as nx
import franken_networkx as fnx


def _graphs():
    return fnx.Graph([(0, 1), (1, 2)]), nx.Graph([(0, 1), (1, 2)])


@pytest.mark.parametrize(
    "source,target",
    [("x", 2), (0, "y"), ("x", "y"), ("missing", 1)],
)
def test_bidirectional_shortest_path_node_not_found_matches_networkx(source, target):
    fg, ng = _graphs()
    with pytest.raises(nx.NodeNotFound) as fnx_exc:
        fnx.bidirectional_shortest_path(fg, source, target)
    with pytest.raises(nx.NodeNotFound) as nx_exc:
        nx.bidirectional_shortest_path(ng, source, target)
    assert str(fnx_exc.value) == str(nx_exc.value)


def test_bidirectional_message_is_unquoted():
    fg, _ = _graphs()
    with pytest.raises(nx.NodeNotFound) as exc:
        fnx.bidirectional_shortest_path(fg, "x", 2)
    assert str(exc.value) == "Source x is not in G"
    assert "'x'" not in str(exc.value)


def test_bidirectional_valid_query_unaffected():
    fg, ng = _graphs()
    assert fnx.bidirectional_shortest_path(fg, 0, 2) == nx.bidirectional_shortest_path(ng, 0, 2)
