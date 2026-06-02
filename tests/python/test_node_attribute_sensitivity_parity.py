"""Node-attribute-sensitivity parity net.

Completes the sensitivity-net trilogy (direction, weight, node-attribute) that
guards the recurring "kernel silently drops a semantic dimension" bug class.
Assortativity-by-attribute, attribute mixing, and numeric assortativity all
read NODE attributes; a kernel that ignored the named attribute would return a
fixed/degenerate value and pass any test that doesn't vary the attribute. This
harness asserts both (1) parity with networkx and (2) that the result actually
depends on the attribute values (non-vacuity).
"""

import math

import networkx as nx
import franken_networkx as fnx

import pytest


def _graph(mod, cats, nums):
    g = mod.Graph([(0, 1), (1, 2), (2, 3), (3, 0), (0, 2), (2, 4), (4, 5), (5, 3), (1, 4)])
    for n in g:
        g.nodes[n]["color"] = cats[n]
        g.nodes[n]["val"] = nums[n]
    return g


_CATS = {0: "r", 1: "b", 2: "r", 3: "b", 4: "r", 5: "g"}
_NUMS = {0: 1.0, 1: 2.0, 2: 1.0, 3: 3.0, 4: 2.0, 5: 1.0}
# A different attribute assignment, to prove the measures depend on the attr.
_CATS2 = {0: "r", 1: "r", 2: "r", 3: "b", 4: "b", 5: "b"}
_NUMS2 = {0: 5.0, 1: 5.0, 2: 5.0, 3: 0.0, 4: 0.0, 5: 0.0}


def test_attribute_assortativity_matches_networkx():
    gn, gf = _graph(nx, _CATS, _NUMS), _graph(fnx, _CATS, _NUMS)
    assert abs(
        nx.attribute_assortativity_coefficient(gn, "color")
        - fnx.attribute_assortativity_coefficient(gf, "color")
    ) <= 1e-9


def test_numeric_assortativity_matches_networkx():
    gn, gf = _graph(nx, _CATS, _NUMS), _graph(fnx, _CATS, _NUMS)
    assert abs(
        nx.numeric_assortativity_coefficient(gn, "val")
        - fnx.numeric_assortativity_coefficient(gf, "val")
    ) <= 1e-9


def test_attribute_assortativity_depends_on_attribute():
    # Two different colorings must give different assortativity, or the kernel
    # could be ignoring the attribute.
    a = fnx.attribute_assortativity_coefficient(_graph(fnx, _CATS, _NUMS), "color")
    b = fnx.attribute_assortativity_coefficient(_graph(fnx, _CATS2, _NUMS), "color")
    assert abs(a - b) > 1e-6


def test_numeric_assortativity_depends_on_attribute():
    a = fnx.numeric_assortativity_coefficient(_graph(fnx, _CATS, _NUMS), "val")
    b = fnx.numeric_assortativity_coefficient(_graph(fnx, _CATS, _NUMS2), "val")
    assert abs(a - b) > 1e-6


def test_attribute_mixing_dict_matches_networkx():
    gn, gf = _graph(nx, _CATS, _NUMS), _graph(fnx, _CATS, _NUMS)
    dn = {k: dict(v) for k, v in nx.attribute_mixing_dict(gn, "color").items()}
    df = {k: dict(v) for k, v in fnx.attribute_mixing_dict(gf, "color").items()}
    assert dn == df


def test_node_attribute_xy_matches_networkx():
    gn, gf = _graph(nx, _CATS, _NUMS), _graph(fnx, _CATS, _NUMS)
    xn = sorted((a, b) for a, b in nx.node_attribute_xy(gn, "color"))
    xf = sorted((a, b) for a, b in fnx.node_attribute_xy(gf, "color"))
    assert xn == xf


def test_min_cost_flow_uses_node_demand():
    # min_cost_flow reads the node 'demand' attribute; verify cost parity and
    # that a feasible flow is found.
    def build(mod):
        g = mod.DiGraph()
        g.add_node(0, demand=-5)
        g.add_node(3, demand=5)
        for u, v, c, w in [(0, 1, 4, 1), (0, 2, 3, 2), (1, 3, 3, 1), (2, 3, 3, 1), (1, 2, 2, 1)]:
            g.add_edge(u, v, capacity=c, weight=w)
        return g
    assert fnx.min_cost_flow_cost(build(fnx)) == nx.min_cost_flow_cost(build(nx))


@pytest.mark.parametrize("attr", ["color", "val"])
def test_set_get_node_attributes_roundtrip(attr):
    def rt(mod):
        g = mod.path_graph(4)
        mod.set_node_attributes(g, {0: "x", 1: "y", 2: "z"}, attr)
        return mod.get_node_attributes(g, attr)
    assert rt(fnx) == rt(nx)
