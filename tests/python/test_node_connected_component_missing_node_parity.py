"""Parity for ``node_connected_component`` missing-node exception.

networkx's ``node_connected_component`` runs a plain BFS that indexes
``G._adj[n]``, so a missing (hashable) node surfaces as a bare
``KeyError(n)``. fnx previously raised ``NodeNotFound`` from the native
binding. This locks fnx to nx's exception type and args. The unhashable
path (TypeError) and valid queries are unaffected. br-r37-c1-eun8y
"""

from __future__ import annotations

import pytest
import networkx as nx
import franken_networkx as fnx


def _graphs():
    return fnx.Graph([(0, 1), (1, 2), (5, 6)]), nx.Graph([(0, 1), (1, 2), (5, 6)])


@pytest.mark.parametrize("missing", ["x", 99, ("a", "b")])
def test_missing_node_raises_keyerror_like_networkx(missing):
    fg, ng = _graphs()
    with pytest.raises(KeyError) as fnx_exc:
        fnx.node_connected_component(fg, missing)
    with pytest.raises(KeyError) as nx_exc:
        nx.node_connected_component(ng, missing)
    assert fnx_exc.value.args == nx_exc.value.args == (missing,)


@pytest.mark.parametrize("unhashable", [[1, 2], {1: 2}])
def test_unhashable_node_raises_typeerror_like_networkx(unhashable):
    fg, ng = _graphs()
    with pytest.raises(TypeError):
        fnx.node_connected_component(fg, unhashable)
    with pytest.raises(TypeError):
        nx.node_connected_component(ng, unhashable)


def test_valid_query_matches_networkx():
    fg, ng = _graphs()
    assert fnx.node_connected_component(fg, 0) == nx.node_connected_component(ng, 0)
    assert fnx.node_connected_component(fg, 5) == nx.node_connected_component(ng, 5)
