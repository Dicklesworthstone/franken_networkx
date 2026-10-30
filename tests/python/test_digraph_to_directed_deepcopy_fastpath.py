"""Regression coverage for native graph conversion copies.

Conversion copies graph data into a mutable result. Each graph, node and edge
attribute dictionary gets an independent deepcopy; aliases within a dictionary
survive, while aliases between dictionaries do not. Frozen flags and arbitrary
Python instance state are excluded. Native structural copying must also preserve
conversion ordering and store-only edge attributes.
"""

import copy
import random

import networkx as nx
import pytest

import franken_networkx as fnx


def _estrict(a, b):
    ea = {(u, v): d for u, v, d in a.edges(data=True)}
    eb = {(u, v): d for u, v, d in b.edges(data=True)}
    return (
        dict(a.nodes(data=True)) == dict(b.nodes(data=True))
        and a.graph == b.graph
        and ea == eb
        and list(a.nodes) == list(b.nodes)
        and list(a.edges) == list(b.edges)
        and a.is_directed() == b.is_directed()
        and a.is_multigraph() == b.is_multigraph()
    )


def test_to_directed_byte_exact_vs_networkx():
    for seed in range(60):
        r = random.Random(seed)
        nn = r.randint(0, 25)
        nodes = [(i, {"w": r.random(), "tag": [i]}) for i in range(nn)]
        edges = (
            [
                (r.randrange(nn), r.randrange(nn), {"weight": r.random(), "lst": [r.randint(0, 3)]})
                for _ in range(r.randint(0, 70))
            ]
            if nn
            else []
        )
        gf, gx = fnx.DiGraph(), nx.DiGraph()
        gf.graph["m"] = {"k": [seed]}
        gx.graph["m"] = {"k": [seed]}
        gf.add_nodes_from([(n, copy.deepcopy(d)) for n, d in nodes])
        gx.add_nodes_from([(n, copy.deepcopy(d)) for n, d in nodes])
        gf.add_edges_from([(u, v, copy.deepcopy(d)) for u, v, d in edges])
        gx.add_edges_from([(u, v, copy.deepcopy(d)) for u, v, d in edges])
        assert _estrict(gf.to_directed(), gx.to_directed()), seed


def test_batch_built_edge_attrs_survive():
    # Batch-built graphs keep edge attrs in the native store with a lazy
    # mirror. The deepcopy fast path must preserve them.
    gf, gx = fnx.DiGraph(), nx.DiGraph()
    gf.add_nodes_from(range(5))
    gx.add_nodes_from(range(5))
    gf.add_weighted_edges_from([(0, 1, 2.5), (1, 2, 3.5)])
    gx.add_weighted_edges_from([(0, 1, 2.5), (1, 2, 3.5)])
    rf, rx = gf.to_directed(), gx.to_directed()
    assert _estrict(rf, rx)
    assert {(u, v): d for u, v, d in rf.edges(data=True)} == {
        (0, 1): {"weight": 2.5},
        (1, 2): {"weight": 3.5},
    }


def test_result_independent_from_source():
    gf = fnx.DiGraph()
    gf.graph["m"] = ["orig"]
    gf.add_node(0, tag=["n0"])
    gf.add_edge(1, 2, lst=["e12"])
    r = gf.to_directed()
    gf.graph["m"].append("MUT")
    gf.nodes[0]["tag"].append("MUT")
    gf[1][2]["lst"].append("MUT")
    gf.add_edge(9, 8)
    assert "MUT" not in r.graph["m"]
    assert "MUT" not in r.nodes[0]["tag"]
    assert "MUT" not in r[1][2]["lst"]
    assert 9 not in r


def test_as_view_still_returns_view():
    gf = fnx.DiGraph([(0, 1, {"weight": 1.0})])
    v = gf.to_directed(as_view=True)
    assert v.is_directed()
    assert list(v.edges(data=True)) == [(0, 1, {"weight": 1.0})]


def test_subclass_falls_through():
    class Sub(fnx.DiGraph):
        pass

    s = Sub()
    s.add_edge(0, 1, weight=2.0)
    r = s.to_directed()
    # to_directed_class() default is DiGraph, so result is a plain DiGraph
    assert {(u, v): d for u, v, d in r.edges(data=True)} == {(0, 1): {"weight": 2.0}}


def test_empty_graph():
    assert _estrict(fnx.DiGraph().to_directed(), nx.DiGraph().to_directed())


def test_graph_to_undirected_byte_exact_vs_networkx():
    # Symmetric fast path: an already-undirected Graph's to_undirected() is a deep
    # copy into the same class.
    for seed in range(60):
        r = random.Random(seed)
        nn = r.randint(0, 25)
        nodes = [(i, {"w": r.random(), "tag": [i]}) for i in range(nn)]
        edges = (
            [(r.randrange(nn), r.randrange(nn), {"weight": r.random(), "lst": [r.randint(0, 3)]})
             for _ in range(r.randint(0, 70))]
            if nn
            else []
        )
        gf, gx = fnx.Graph(), nx.Graph()
        gf.graph["m"] = {"k": [seed]}
        gx.graph["m"] = {"k": [seed]}
        gf.add_nodes_from([(n, copy.deepcopy(d)) for n, d in nodes])
        gx.add_nodes_from([(n, copy.deepcopy(d)) for n, d in nodes])
        gf.add_edges_from([(u, v, copy.deepcopy(d)) for u, v, d in edges])
        gx.add_edges_from([(u, v, copy.deepcopy(d)) for u, v, d in edges])
        assert _estrict(gf.to_undirected(), gx.to_undirected()), seed


def test_digraph_to_undirected_collapse_untouched():
    # DiGraph.to_undirected COLLAPSES reciprocal edges (not a deepcopy) and must
    # stay correct (the fast path deliberately does not touch it).
    gf, gx = fnx.DiGraph(), nx.DiGraph()
    for g in (gf, gx):
        g.add_edges_from(
            [(0, 1, {"weight": 1.0}), (1, 0, {"weight": 2.0}), (2, 3, {"weight": 5.0})]
        )
    assert _estrict(gf.to_undirected(), gx.to_undirected())


def test_graph_to_undirected_batch_built_weights_survive():
    gf, gx = fnx.Graph(), nx.Graph()
    gf.add_nodes_from(range(5))
    gx.add_nodes_from(range(5))
    gf.add_weighted_edges_from([(0, 1, 2.5), (1, 2, 3.5)])
    gx.add_weighted_edges_from([(0, 1, 2.5), (1, 2, 3.5)])
    assert _estrict(gf.to_undirected(), gx.to_undirected())


def test_graph_to_undirected_as_view_and_empty():
    v = fnx.Graph([(0, 1, {"weight": 1.0})]).to_undirected(as_view=True)
    assert not v.is_directed()
    assert _estrict(fnx.Graph().to_undirected(), nx.Graph().to_undirected())


_GRAPH_CLASSES = ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph")
_CONVERSIONS = ("to_directed", "to_undirected")


@pytest.mark.parametrize("graph_class", _GRAPH_CLASSES)
@pytest.mark.parametrize("conversion", _CONVERSIONS)
@pytest.mark.parametrize("attributed", [False, True])
def test_conversion_of_frozen_graph_returns_mutable_copy(
    graph_class, conversion, attributed
):
    for lib in (nx, fnx):
        graph = getattr(lib, graph_class)()
        graph.add_edge("source", "target", **({"payload": [1]} if attributed else {}))
        lib.freeze(graph)

        converted = getattr(graph, conversion)()

        assert not lib.is_frozen(converted)
        converted.add_edge("new", "target")
        assert "new" not in graph
        assert lib.is_frozen(graph)


@pytest.mark.parametrize("graph_class", _GRAPH_CLASSES)
@pytest.mark.parametrize("conversion", _CONVERSIONS)
def test_conversion_ignores_custom_instance_state(graph_class, conversion):
    for lib in (nx, fnx):
        copied_state = []

        class ApplicationState:
            def __deepcopy__(self, memo):
                copied_state.append(True)
                raise AssertionError("conversion copied application instance state")

        graph = getattr(lib, graph_class)()
        graph.add_edge("source", "target")
        graph.application_state = ApplicationState()

        converted = getattr(graph, conversion)()

        assert not copied_state
        assert "application_state" not in vars(converted)
        assert list(converted) == list(graph)


@pytest.mark.parametrize("graph_class", _GRAPH_CLASSES)
@pytest.mark.parametrize("conversion", _CONVERSIONS)
def test_conversion_deepcopies_each_attribute_dictionary_independently(
    graph_class, conversion
):
    for lib in (nx, fnx):
        graph = getattr(lib, graph_class)()
        shared = ["source"]
        attrs = {"first": shared, "second": shared}
        graph.graph.update(attrs)
        graph.add_nodes_from([("a", attrs), ("b", attrs), ("c", attrs)])
        graph.add_edges_from([("a", "b", attrs), ("b", "c", attrs)])

        converted = getattr(graph, conversion)()
        dictionaries = [converted.graph]
        dictionaries.extend(data for _, data in converted.nodes(data=True))
        dictionaries.extend(data for *_, data in converted.edges(data=True))
        values = [data["first"] for data in dictionaries]

        assert all(data["first"] is data["second"] for data in dictionaries)
        assert all(value == shared and value is not shared for value in values)
        assert len({id(value) for value in values}) == len(values)
        values[0].append("changed")
        assert all(value == ["source"] for value in values[1:])
        assert shared == ["source"]


@pytest.mark.parametrize("graph_class", _GRAPH_CLASSES)
@pytest.mark.parametrize("conversion", _CONVERSIONS)
def test_conversion_keeps_original_node_objects(graph_class, conversion):
    class Node:
        def __deepcopy__(self, memo):
            raise AssertionError("conversion must preserve node objects")

    for lib in (nx, fnx):
        graph = getattr(lib, graph_class)()
        source, target = Node(), Node()
        graph.add_edge(source, target, payload=[1])

        converted = getattr(graph, conversion)()

        assert list(converted)[0] is source
        assert list(converted)[1] is target


@pytest.mark.parametrize("attributed", [False, True])
def test_directed_conversion_rebuilds_predecessor_order(attributed):
    results = []
    for lib in (nx, fnx):
        graph = lib.DiGraph()
        graph.add_nodes_from(["first", "middle", "last", "sink"])
        for source in ("last", "first", "middle"):
            graph.add_edge(
                source,
                "sink",
                **({"payload": [source]} if attributed else {}),
            )
        assert list(graph.pred["sink"]) == ["last", "first", "middle"]

        converted = graph.to_directed()

        assert list(converted.pred["sink"]) == ["first", "middle", "last"]
        assert list(graph.pred["sink"]) == ["last", "first", "middle"]
        results.append((list(converted), list(converted.edges(data=True))))
    assert results[0] == results[1]


@pytest.mark.parametrize("source_mode", ["strict", "hardened"])
@pytest.mark.parametrize("attributed", [False, True])
def test_directed_conversion_keeps_source_mode_with_fresh_history(
    source_mode, attributed
):
    with fnx.compatibility_mode(source_mode):
        graph = fnx.DiGraph()
        graph.graph["payload"] = ["source"]
        graph.add_node(0, **({"payload": [0]} if attributed else {}))
        graph.add_edge(0, 1, **({"payload": [1]} if attributed else {}))
    source_records = graph.decision_records()
    ambient_mode = "hardened" if source_mode == "strict" else "strict"

    with fnx.compatibility_mode(ambient_mode):
        converted = graph.to_directed()
        assert fnx.get_compatibility_mode() == ambient_mode

    assert converted.mode == source_mode
    assert converted.compatibility_mode == source_mode
    assert converted.decision_records() == []
    assert graph.decision_records() == source_records
    converted.graph["payload"].append("copy")
    assert graph.graph["payload"] == ["source"]


@pytest.mark.parametrize("graph_class", _GRAPH_CLASSES)
@pytest.mark.parametrize("conversion", _CONVERSIONS)
def test_conversion_view_still_shares_data_and_follows_source(
    graph_class, conversion
):
    for lib in (nx, fnx):
        graph = getattr(lib, graph_class)()
        graph.add_edge(0, 1, payload=["source"])
        view = getattr(graph, conversion)(as_view=True)

        assert lib.is_frozen(view)
        view_attrs = view[0][1][0] if view.is_multigraph() else view[0][1]
        source_attrs = graph[0][1][0] if graph.is_multigraph() else graph[0][1]
        view_attrs["payload"].append("view")
        assert source_attrs["payload"] == ["source", "view"]
        with pytest.raises(lib.NetworkXError):
            view.add_edge(2, 3)
        graph.add_edge(1, 2)
        assert 2 in view


@pytest.mark.parametrize("source_mode", ["strict", "hardened"])
@pytest.mark.parametrize(
    "mutation", ["graph_add_node", "node_add_edge", "node_remove_edge", "node_edit_edge"]
)
def test_directed_conversion_observes_deepcopy_callback_mutations(source_mode, mutation):
    results = []
    ambient_mode = "hardened" if source_mode == "strict" else "strict"
    for lib in (nx, fnx):
        with fnx.compatibility_mode(source_mode):
            graph = lib.DiGraph()
            graph.add_nodes_from(["a", "b", "c"])
            graph.add_edge("a", "b", payload=["original"])
            if mutation in ("node_remove_edge", "node_edit_edge"):
                graph.add_edge("b", "c", payload=["before"])
        callback_modes = []

        class Callback:
            def __deepcopy__(self, memo):
                callback_modes.append(fnx.get_compatibility_mode())
                if mutation == "graph_add_node":
                    graph.add_node("added", payload=["new"])
                    graph.add_edge("added", "a", payload=["new"])
                elif mutation == "node_add_edge":
                    graph.add_edge("b", "c", payload=["new"])
                elif mutation == "node_remove_edge":
                    graph.remove_edge("b", "c")
                else:
                    graph["b"]["c"]["payload"] = ["new"]
                return "copied"

        if mutation == "graph_add_node":
            graph.graph["hook"] = Callback()
        else:
            graph.nodes["a"]["hook"] = Callback()
        with fnx.compatibility_mode(ambient_mode):
            converted = graph.to_directed()
            assert fnx.get_compatibility_mode() == ambient_mode
        assert callback_modes == [ambient_mode]
        results.append(
            (dict(converted.graph), list(converted.nodes(data=True)), list(converted.edges(data=True)))
        )
    assert results[0] == results[1]
