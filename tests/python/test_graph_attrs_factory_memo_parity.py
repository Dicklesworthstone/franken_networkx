"""br-r37-c1-7q6wh — the graph-attrs factory question is per CLASS.

`G.graph` is a `_GraphAttrsDescriptor`, and its `__get__` ran
`getattr(objtype, "graph_attr_dict_factory", dict)` — a full MRO walk — on every
access. `G.name` is `self.graph.get("name", "")`, so it paid the walk too. That
is why `G.name` measured 0.215x-0.220x against networkx uniformly on all four
classes: networkx's `graph` is a plain instance attribute, fnx's is a descriptor.

    paired memo-off vs memo-on, same invocation, balanced square,
    21 rounds x 20000 reps: 0.3091us -> 0.2350us, 1.3081x CI [1.3032, 1.3152]
    A/A nulls 0.9986 and 1.0007, both PASS.

Whether a class overrides the factory cannot differ between instances of it, so
the answer is memoised per class — the same shape as br-r37-c1-vaayu and
br-r37-c1-8itxk. The per-INSTANCE override check is untouched.

WHAT NEEDS LOCKING is that memoising a CLASS-level answer does not break the
per-class distinctions it collapses: a subclass with a custom factory must still
get its container, a sibling must not inherit that answer, and the assignment
contract on `G.graph` must be unchanged.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


@pytest.mark.parametrize("cls_name", CLASSES)
def test_graph_and_name_match_networkx(cls_name):
    gnx, gfx = getattr(nx, cls_name)(), getattr(fnx, cls_name)()
    assert gfx.name == gnx.name == ""
    for graph in (gnx, gfx):
        graph.graph["name"] = "fixture"
        graph.graph["other"] = 7
    assert gfx.name == gnx.name == "fixture"
    assert dict(gfx.graph) == dict(gnx.graph)
    assert type(gfx.graph) is type(gnx.graph) is dict


@pytest.mark.parametrize("cls_name", CLASSES)
def test_a_custom_factory_is_still_honoured(cls_name):
    """br-r37-c1-gattfact: the behaviour the memoised branch guards."""

    class Odd(dict):
        pass

    Sub = type("Sub", (getattr(fnx, cls_name),), {"graph_attr_dict_factory": Odd})
    graph = Sub()
    graph.graph["k"] = "v"
    assert type(graph.graph) is Odd
    assert dict(graph.graph) == {"k": "v"}
    assert graph.name == ""
    graph.graph["name"] = "n"
    assert graph.name == "n"


@pytest.mark.parametrize("cls_name", CLASSES)
def test_the_memo_does_not_leak_between_sibling_classes(cls_name):
    """A per-class memo must not answer for a different class.

    Two subclasses of the same base, one with a custom factory and one without,
    must each get their own answer regardless of which is touched first.
    """

    class Odd(dict):
        pass

    base = getattr(fnx, cls_name)
    Custom = type("Custom", (base,), {"graph_attr_dict_factory": Odd})
    Plain = type("Plain", (base,), {})
    custom_first = Custom()
    custom_first.graph["a"] = 1
    plain = Plain()
    plain.graph["b"] = 2
    assert type(custom_first.graph) is Odd
    assert type(plain.graph) is dict, "the custom answer leaked to a sibling"
    # and in the other order
    plain_first = Plain()
    plain_first.graph["c"] = 3
    custom_second = Custom()
    custom_second.graph["d"] = 4
    assert type(plain_first.graph) is dict
    assert type(custom_second.graph) is Odd, "the plain answer leaked to a sibling"


@pytest.mark.parametrize("cls_name", CLASSES)
def test_graph_assignment_identity_contract_is_unchanged(cls_name):
    """br-grattrident: `before is G.graph` must hold across assignment."""
    graph = getattr(fnx, cls_name)()
    graph.graph["a"] = 1
    before = graph.graph
    graph.graph = {"b": 2}
    assert graph.graph is before
    assert dict(graph.graph) == {"b": 2}


@pytest.mark.parametrize("cls_name", CLASSES)
def test_in_place_or_still_keeps_merged_contents(cls_name):
    """br-r37-c1-iorgrf: `g.graph |= other` desugars through __set__."""
    gnx, gfx = getattr(nx, cls_name)(), getattr(fnx, cls_name)()
    for graph in (gnx, gfx):
        graph.graph["a"] = 1
        graph.graph |= {"b": 2}
    assert dict(gfx.graph) == dict(gnx.graph) == {"a": 1, "b": 2}


def test_the_memo_is_actually_populated():
    """Non-vacuity: if the cache never fills, the lever is dead code."""
    fnx._GRAPH_ATTR_FACTORY_CACHE.clear()
    graph = fnx.Graph()
    graph.graph  # noqa: B018 - the access under test
    assert fnx.Graph in fnx._GRAPH_ATTR_FACTORY_CACHE
    assert fnx._GRAPH_ATTR_FACTORY_CACHE[fnx.Graph] is dict
