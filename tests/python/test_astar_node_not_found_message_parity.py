"""Golden parity for ``astar_path`` NodeNotFound message wording.

``astar_path`` used to leak the native binding's repr-quoted wording
(``Source 'x' is not in G``) when the source or target node was absent,
whereas networkx emits the unquoted ``Source x is not in G`` (source
checked first, then target). The Python wrapper only translated the
``ValueError`` no-path case, not ``NodeNotFound``. ``astar_path_length``
already matched nx (it uses the ``Either source ... or target ...``
form).

This locks the message and exception type against the real upstream
library. br-r37-c1-yx0sh
"""

from __future__ import annotations

import pytest
import networkx as nx
import franken_networkx as fnx


def _graphs():
    return fnx.Graph([(0, 1), (1, 2)]), nx.Graph([(0, 1), (1, 2)])


@pytest.mark.parametrize(
    "source,target",
    [
        ("x", 1),   # missing source
        (0, "y"),   # missing target
        ("x", "y"),  # both missing -> source reported first
        ("x", 2),
        (0, "missing"),
    ],
)
def test_astar_path_node_not_found_matches_networkx(source, target):
    fg, ng = _graphs()
    with pytest.raises(nx.NodeNotFound) as fnx_exc:
        fnx.astar_path(fg, source, target)
    with pytest.raises(nx.NodeNotFound) as nx_exc:
        nx.astar_path(ng, source, target)
    assert str(fnx_exc.value) == str(nx_exc.value)


@pytest.mark.parametrize(
    ("fnx_graph_factory", "nx_graph_factory"),
    [
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
@pytest.mark.parametrize(
    "source,target",
    [
        ("x", 1),
        (0, "y"),
        ("x", "y"),
    ],
)
def test_astar_path_directed_node_not_found_matches_networkx(
    fnx_graph_factory, nx_graph_factory, source, target
):
    fg = fnx_graph_factory([(0, 1), (1, 2)])
    ng = nx_graph_factory([(0, 1), (1, 2)])

    with pytest.raises(nx.NodeNotFound) as fnx_exc:
        fnx.astar_path(fg, source, target)
    with pytest.raises(nx.NodeNotFound) as nx_exc:
        nx.astar_path(ng, source, target)

    assert str(fnx_exc.value) == str(nx_exc.value)


def test_astar_path_message_is_unquoted_string_form():
    fg, _ = _graphs()
    with pytest.raises(nx.NodeNotFound) as exc:
        fnx.astar_path(fg, "x", 1)
    # The string key must appear unquoted, exactly as networkx formats it.
    assert str(exc.value) == "Source x is not in G"
    assert "'x'" not in str(exc.value)


def test_astar_path_length_message_still_matches_networkx():
    fg, ng = _graphs()
    for source, target in [("x", 1), (0, "y"), ("x", "y")]:
        with pytest.raises(nx.NodeNotFound) as fnx_exc:
            fnx.astar_path_length(fg, source, target)
        with pytest.raises(nx.NodeNotFound) as nx_exc:
            nx.astar_path_length(ng, source, target)
        assert str(fnx_exc.value) == str(nx_exc.value)


def test_astar_path_valid_query_unaffected():
    fg, ng = _graphs()
    assert fnx.astar_path(fg, 0, 2) == nx.astar_path(ng, 0, 2)
    # source == target returns the trivial path.
    assert fnx.astar_path(fg, 1, 1) == nx.astar_path(ng, 1, 1)
