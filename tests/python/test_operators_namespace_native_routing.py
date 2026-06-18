"""``franken_networkx.operators`` binary operators route to fnx natives.

The product / ``*_all`` operators already routed to fnx, but the binary
operators (union/compose/complement/difference/intersection/
symmetric_difference/reverse/full_join) were left as networkx's ``import *``
versions, which return an ``nx.Graph`` (a drop-in type bug) instead of an
fnx graph. These now route to the fnx-native implementations.

br-r37-c1-2qsqf
"""

from __future__ import annotations

import pytest
import networkx as nx
import franken_networkx as fnx
from franken_networkx import operators as fnx_operators

_BINARY_OPS = [
    "union",
    "compose",
    "complement",
    "difference",
    "intersection",
    "symmetric_difference",
    "reverse",
    "full_join",
]


@pytest.mark.parametrize("name", _BINARY_OPS)
def test_operator_is_not_networkx_version(name):
    op = getattr(fnx_operators, name)
    if hasattr(nx, name):
        assert op is not getattr(nx, name)


def _fnx_graph(obj):
    return type(obj).__module__.startswith("franken_networkx")


def test_binary_operators_return_fnx_graphs_matching_networkx():
    g = fnx.Graph([(0, 1), (1, 2), (2, 0)])
    h = fnx.Graph([(3, 4), (4, 5)])
    ng = nx.Graph([(0, 1), (1, 2), (2, 0)])
    nh = nx.Graph([(3, 4), (4, 5)])

    def _edges(graph):
        return sorted(tuple(sorted(e)) for e in graph.edges())

    for op, args, nargs in [
        ("compose", (g, h), (ng, nh)),
        ("complement", (g,), (ng,)),
        ("full_join", (g, h), (ng, nh)),
    ]:
        result = getattr(fnx_operators, op)(*args)
        expected = getattr(nx, op)(*nargs)
        assert _fnx_graph(result), f"{op} did not return an fnx graph"
        assert _edges(result) == _edges(expected)


def test_directed_reverse_returns_fnx_graph():
    dg = fnx.DiGraph([(0, 1), (1, 2)])
    rev = fnx_operators.reverse(dg)
    assert type(rev).__module__.startswith("franken_networkx")
    assert sorted(rev.edges()) == [(1, 0), (2, 1)]
