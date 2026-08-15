"""Deliberate-divergence lock for br-r37-c1-cow38 — custom node-key equality.

fnx canonicalises every node key to a string and compares those bytes, so it
implements ONE equivalence relation: character identity. networkx stores nodes
in a dict, so the key's own ``__eq__``/``__hash__`` define the relation. A node
key that redefines equality therefore matches in networkx and misses in fnx.

That is a DECLARED SCOPE BOUNDARY, not an open defect — see "Declared Scope
Boundary: Node-Key Equivalence" in FEATURE_PARITY.md for why closing it needs a
storage-model change whose cost is itself an open bead
(br-r37-c1-node-storage-materialization-wall-5fije).

This file therefore asserts the divergence FROM BOTH SIDES: networkx matches,
fnx does not. That is unusual and intentional. **If these tests start failing
because fnx began agreeing with networkx, the boundary has moved and
FEATURE_PARITY.md is what needs updating — do not "fix" the test.**

What is NOT a scope boundary, and is asserted as ordinary parity below: a plain
``str`` subclass that does not override anything must behave exactly like
``str`` in both libraries, and the hashability contract (br-r37-c1-lvlu7,
closed in c14dc2ecf) must hold.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


class CaseFoldingStr(str):
    """A node key asserting that 'N0' and 'n0' are the same node."""

    def __hash__(self):
        return hash(str(self).lower())

    def __eq__(self, other):
        return str(self).lower() == str(other).lower()

    def __ne__(self, other):
        return not self.__eq__(other)


class PlainStr(str):
    """A subclass that redefines NOTHING — ordinary parity, not a boundary."""


def _pair(cls_name):
    made = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        graph.add_edge("n0", "n1")
        made.append(graph)
    return made


def _answer(fn, graph):
    try:
        result = fn(graph)
    except Exception as exc:  # noqa: BLE001 - an exception is a valid answer
        return ("raised", type(exc).__name__)
    if isinstance(result, (int, float)):
        return ("number", result)
    try:
        return ("view", sorted(dict(result).items()))
    except TypeError:
        return ("value", result)


PROBES = [
    ("n in G", lambda g, key: key in g),
    ("G.has_node(n)", lambda g, key: g.has_node(key)),
    ("n in G.nodes", lambda g, key: key in g.nodes),
    ("(n,v) in G.edges", lambda g, key: (key, "n1") in g.edges),
    ("G.has_edge(n,v)", lambda g, key: g.has_edge(key, "n1")),
]


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize(("label", "probe"), PROBES, ids=[p[0] for p in PROBES])
def test_custom_equality_key_matches_in_networkx_and_misses_in_fnx(
    cls_name, label, probe
):
    """THE DECLARED DIVERGENCE. Both sides asserted on purpose."""
    gnx, gfx = _pair(cls_name)
    key = CaseFoldingStr("N0")
    assert probe(gnx, key) is True, (
        f"networkx no longer honours custom node-key equality for {label}; "
        "the premise of the scope boundary has changed"
    )
    assert probe(gfx, key) is False, (
        f"fnx now matches networkx for {label} on a custom-equality node key. "
        "That is an IMPROVEMENT, not a regression: update the 'Declared Scope "
        "Boundary: Node-Key Equivalence' section of FEATURE_PARITY.md and this "
        "file rather than reverting the behaviour."
    )


@pytest.mark.parametrize("cls_name", CLASSES)
def test_custom_equality_key_degree_divergence(cls_name):
    """degree() answers a number in networkx and an empty view in fnx."""
    gnx, gfx = _pair(cls_name)
    key = CaseFoldingStr("N0")
    assert _answer(lambda g: g.degree(key), gnx) == ("number", 1)
    assert _answer(lambda g: g.degree(key), gfx) == ("view", [])


@pytest.mark.parametrize("cls_name", CLASSES)
def test_exact_value_key_is_unaffected_by_the_boundary(cls_name):
    """The same subclass spelled with the STORED characters matches in both."""
    gnx, gfx = _pair(cls_name)
    key = CaseFoldingStr("n0")
    for label, probe in PROBES:
        assert probe(gfx, key) == probe(gnx, key) is True, label


@pytest.mark.parametrize("cls_name", CLASSES)
def test_plain_str_subclass_is_full_parity_not_a_boundary(cls_name):
    """A subclass that overrides nothing is ordinary parity in both directions."""
    gnx, gfx = _pair(cls_name)
    for label, probe in PROBES:
        assert probe(gfx, PlainStr("n0")) == probe(gnx, PlainStr("n0")) is True, label
        assert probe(gfx, PlainStr("zz")) == probe(gnx, PlainStr("zz")) is False, label


@pytest.mark.parametrize("cls_name", CLASSES)
def test_hashability_contract_is_in_scope_and_still_holds(cls_name):
    """br-r37-c1-lvlu7: unhashable keys must behave exactly as in networkx."""

    class Unhashable(str):
        __hash__ = None

    gnx, gfx = _pair(cls_name)
    key = Unhashable("n0")
    for label, probe in PROBES:
        assert _answer(lambda g: probe(g, key), gfx) == _answer(
            lambda g: probe(g, key), gnx
        ), label


@pytest.mark.parametrize("cls_name", CLASSES)
def test_custom_equality_key_cannot_corrupt_the_graph_through_add(cls_name):
    """Adding under the alias must not silently merge or duplicate differently
    from a plain unequal key: whatever fnx does, it stays self-consistent."""
    gnx, gfx = _pair(cls_name)
    for graph in (gnx, gfx):
        graph.add_node(CaseFoldingStr("N0"))
    # networkx treats it as the SAME node; fnx as a NEW one. Assert each
    # library's own count so a silent change in either is caught.
    assert gnx.number_of_nodes() == 2
    assert gfx.number_of_nodes() == 3
    # Whatever the count, both libraries must agree with themselves: every
    # node they report must be found by their own membership test.
    for graph in (gnx, gfx):
        assert all(n in graph for n in graph.nodes)
