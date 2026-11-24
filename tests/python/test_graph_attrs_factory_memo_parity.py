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

import copy
import gc
import weakref
from collections import UserDict

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
@pytest.mark.parametrize("mapping_type", [dict, UserDict])
def test_graph_assignment_retains_replacement_reference(cls_name, mapping_type):
    def observe(module):
        graph = getattr(module, cls_name)()
        graph.graph["a"] = 1
        before = graph.graph
        replacement = mapping_type(b=2)
        graph.graph = replacement
        replacement["external"] = 3
        graph.graph["internal"] = 4
        return (
            graph.graph is replacement,
            graph.graph is before,
            dict(before),
            dict(replacement),
            dict(graph.graph),
        )

    assert observe(fnx) == observe(nx)


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("holder_kind", ["none", "dict", "view"])
def test_graph_assignment_releases_obsolete_native_ownership(cls_name, holder_kind):
    def observe(module):
        graph = getattr(module, cls_name)()

        class Value:
            pass

        value = Value()
        reference = weakref.ref(value)
        graph.graph["value"] = value
        del value
        if holder_kind == "dict":
            holder = graph.graph
        elif holder_kind == "view":
            holder = graph.copy(as_view=True)
        else:
            holder = None
        graph.graph = {"replacement": 1}
        released_on_assignment = reference() is None
        if holder_kind == "dict":
            retained_contents = holder.get("value") is reference()
        elif holder_kind == "view":
            retained_contents = holder.graph.get("value") is reference()
        else:
            retained_contents = False
        holder = None
        gc.collect()
        return released_on_assignment, retained_contents, reference() is None

    assert observe(fnx) == observe(nx)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_graph_assignment_finalizer_can_reenter_replacement(cls_name):
    def observe(module):
        graph = getattr(module, cls_name)()
        observations = []

        class OnReplace:
            def __del__(self):
                try:
                    observations.append(("metadata", dict(graph.graph)))
                    graph.graph = {"from_finalizer": 2}
                    graph.add_edge(2, 3)
                except Exception as exc:
                    observations.append(("error", type(exc).__name__, str(exc)))

        graph.graph["value"] = OnReplace()
        replacement = {"replacement": 1}
        graph.graph = replacement
        return (
            observations,
            graph.graph is replacement,
            dict(graph.graph),
            list(graph),
            list(graph.edges),
        )

    assert observe(fnx) == observe(nx)


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("metadata_kind", ["native", "assigned", "factory"])
def test_clear_preserves_current_metadata_identity(cls_name, metadata_kind):
    def observe(module):
        graph_type = getattr(module, cls_name)
        if metadata_kind == "factory":
            graph_type = type("Custom", (graph_type,), {"graph_attr_dict_factory": UserDict})
        graph = graph_type()
        graph.add_edge(0, 1)
        if metadata_kind == "assigned":
            graph.graph = {"name": "assigned"}
        graph.graph["data"] = [1, 2]
        held = graph.graph
        graph.clear()
        empty = dict(held)
        held["after"] = 3
        return (
            graph.graph is held,
            type(graph.graph),
            empty,
            dict(graph.graph),
            list(graph),
            list(graph.edges),
        )

    assert observe(fnx) == observe(nx)


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("view_kind", ["shallow", "copy_view", "subgraph", "nx_view"])
def test_graph_metadata_aliases_survive_reference_replacement(cls_name, view_kind):
    def observe(module):
        graph = getattr(module, cls_name)()
        graph.add_edge(0, 1)
        graph.graph["original"] = 1
        if view_kind == "shallow":
            view = copy.copy(graph)
        elif view_kind == "copy_view":
            view = graph.copy(as_view=True)
        elif view_kind == "subgraph":
            view = graph.subgraph([0, 1])
        else:
            view = nx.graphviews.generic_graph_view(graph)
        held = graph.graph
        initially_shared = view.graph is held
        graph.graph = {"replacement": 2}
        view.graph["through_view"] = 3
        return (
            initially_shared,
            view.graph is held,
            graph.graph is held,
            dict(held),
            dict(graph.graph),
            dict(view.graph),
        )

    assert observe(fnx) == observe(nx)


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("replacement_target", ["neither", "source", "copy"])
@pytest.mark.parametrize("clear_target", ["source", "copy"])
def test_clear_shared_storage_only_clears_callers_metadata(
    cls_name, replacement_target, clear_target
):
    def observe(module):
        source = getattr(module, cls_name)()
        source.add_edge(0, 1)
        source.graph["original"] = 1
        held = source.graph
        clone = copy.copy(source)
        graphs = {"source": source, "copy": clone}
        replacement = {"replacement": 2}
        if replacement_target != "neither":
            graphs[replacement_target].graph = replacement
        graphs[clear_target].clear()
        return (
            source.graph is held,
            clone.graph is held,
            source.graph is replacement,
            clone.graph is replacement,
            dict(held),
            dict(replacement),
            dict(source.graph),
            dict(clone.graph),
            list(source),
            list(clone),
        )

    assert observe(fnx) == observe(nx)


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("storage_kind", ["native", "shared", "assigned"])
def test_metadata_clear_hook_observes_empty_topology_once(cls_name, storage_kind):
    def observe(module):
        graph = getattr(module, cls_name)()
        graph.add_edge(0, 1)
        if storage_kind == "shared":
            graph = copy.copy(graph)
        elif storage_kind == "assigned":
            graph._node = {0: {}, 1: {}}
            edge = {0: {}} if graph.is_multigraph() else {}
            graph._adj = {0: {1: edge}, 1: {}}
            if graph.is_directed():
                graph._pred = {0: {}, 1: {0: edge}}
            else:
                graph._adj[1][0] = edge
        observations = []

        class Metadata(UserDict):
            def clear(self):
                observations.append((list(graph), list(graph.edges), dict(self)))
                super().clear()
                graph.add_edge(2, 3)

        metadata = Metadata(marker=1)
        graph.graph = metadata
        graph.clear()
        return (
            observations,
            graph.graph is metadata,
            dict(metadata),
            list(graph),
            list(graph.edges),
        )

    assert observe(fnx) == observe(nx)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_replacement_metadata_survives_copies_and_node_link_export(cls_name):
    def observe(module):
        graph = getattr(module, cls_name)()
        graph.add_edge(0, 1)
        held = graph.graph
        held["original"] = 1
        nested = [1]
        replacement = {"nested": nested}
        graph.graph = replacement
        replacement["late"] = 2
        duplicate = graph.copy()
        converted = getattr(module, cls_name)(graph)
        exported = module.node_link_data(graph)
        replacement["after"] = 3
        return (
            dict(held),
            dict(graph.graph),
            dict(duplicate.graph),
            dict(converted.graph),
            exported["graph"] is replacement,
            duplicate.graph is replacement,
            converted.graph is replacement,
            duplicate.graph["nested"] is nested,
            converted.graph["nested"] is nested,
        )

    assert observe(fnx) == observe(nx)


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
