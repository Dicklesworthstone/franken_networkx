"""Contraction must preserve live incident readers and partial mutation state."""

import franken_networkx as fnx
import networkx as nx
import pytest
from franken_networkx import minors as fnx_minors
from networkx.algorithms import minors as nx_minors


GRAPH_TYPES = ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph")


def _contract(module, namespace, function, graph, copy, **kwargs):
    if namespace == "minors":
        module = fnx_minors if module is fnx else nx_minors
    operation = getattr(module, function)
    args = (("u", "v"),) if function == "contracted_edge" else ("u", "v")
    return operation(graph, *args, copy=copy, **kwargs)


@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
@pytest.mark.parametrize("copy", [False, True])
@pytest.mark.parametrize("namespace", ["root", "minors"])
@pytest.mark.parametrize(
    "function", ["contracted_nodes", "identified_nodes", "contracted_edge"]
)
def test_contraction_consumes_incident_readers_at_the_mutation_boundary(
    graph_type, copy, namespace, function
):
    def run(module):
        graph = getattr(module, graph_type)()
        graph.add_nodes_from(["u", "v", "early", "late"])
        graph.add_edge("u", "v")
        target = graph.copy() if copy else graph
        graph.copy = lambda: target
        trace = []
        original_remove = target.remove_node

        def remove(node):
            trace.append("remove")
            original_remove(node)

        target.remove_node = remove

        def incident(direction):
            def reader(*args, **kwargs):
                trace.append(("call", direction))

                def rows():
                    before_removal = "v" in target
                    trace.append(("iterate", direction, before_removal))
                    neighbor = "early" if before_removal else "late"
                    endpoints = (
                        (neighbor, "v") if direction == "in" else ("v", neighbor)
                    )
                    yield (*endpoints, {"before_removal": before_removal})

                return rows()

            return reader

        if graph.is_directed():
            graph.in_edges = incident("in")
            graph.out_edges = incident("out")
        else:
            graph.edges = incident("undirected")
        result = _contract(module, namespace, function, graph, copy)
        return (
            trace,
            result is graph,
            list(result),
            result.has_edge("u", "early"),
            result.has_edge("u", "late"),
            result.get_edge_data("u", "late" if copy else "early"),
            dict(result.nodes["u"]),
        )

    expected = run(nx)
    assert expected[1] is (not copy)
    assert expected[3:5] == (not copy, copy)
    assert run(fnx) == expected


@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
@pytest.mark.parametrize("copy", [False, True])
@pytest.mark.parametrize("store", [None, "contraction"])
@pytest.mark.parametrize("function", ["contracted_nodes", "identified_nodes"])
def test_absent_survivor_keeps_reference_error_and_partial_state(
    graph_type, copy, store, function
):
    def run(module):
        graph = getattr(module, graph_type)()
        graph.add_node("v", payload=[1, 2])
        try:
            result = _contract(
                module, "root", function, graph, copy, store_contraction_as=store
            )
            outcome = ("returned", list(result), result is graph)
        except Exception as error:  # The mutation before failure is observable.
            outcome = (type(error).__name__, error.args)
        return outcome, list(graph)

    expected = run(nx)
    if store is not None:
        assert expected[0] == ("KeyError", ("u",))
    assert expected[1] == (["v"] if copy else [])
    assert run(fnx) == expected
