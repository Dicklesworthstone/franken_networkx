"""br-r37-c1-3qt4m: regression tests for min_cost_flow family
exception class on undirected input.

nx's @not_implemented_for('undirected') raises NetworkXNotImplemented.
fnx previously raised NetworkXError. All 3 wrappers (min_cost_flow,
min_cost_flow_cost, capacity_scaling) inherited the wrong class.
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx


@pytest.mark.parametrize(
    "fn",
    [fnx.min_cost_flow, fnx.min_cost_flow_cost, fnx.capacity_scaling],
)
@pytest.mark.parametrize(
    "cls",
    [fnx.Graph, fnx.MultiGraph],
)
def test_undirected_raises_not_implemented(fn, cls):
    g = cls()
    g.add_edge(0, 1, capacity=1, weight=1)
    with pytest.raises(fnx.NetworkXNotImplemented, match="undirected"):
        fn(g)


def test_directed_still_works():
    g = fnx.DiGraph()
    g.add_edge(0, 1, capacity=2, weight=1)
    g.add_node(0, demand=-1)
    g.add_node(1, demand=1)
    result = fnx.min_cost_flow(g)
    assert isinstance(result, dict)
