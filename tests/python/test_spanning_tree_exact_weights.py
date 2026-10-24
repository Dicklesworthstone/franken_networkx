"""Spanning selectors compare original weights before native f64 conversion."""

from decimal import Decimal
from fractions import Fraction

import networkx as nx
import pytest

import franken_networkx as fnx


def _near_tie_weights(domain, minimum):
    if domain == "fraction":
        low, high = Fraction(1), Fraction(2**54 + 1, 2**54)
    elif domain == "decimal":
        low, high = Decimal(1), Decimal("1.00000000000000001")
    else:
        low, high = 2**53, 2**53 + 1
    return (high, low, low) if minimum else (low, high, high)


def _graph_pair(graph_type, weights, minimum=True):
    payload = {"labels": ["shared"]}
    keys = [object() for _ in range(4)]
    graphs = []
    for library in (fnx, nx):
        graph = getattr(library, graph_type)()
        graph.graph["payload"] = payload
        graph.add_nodes_from((node, {"label": str(node)}) for node in range(3))
        for index, ((u, v), weight) in enumerate(
            zip(((0, 1), (0, 2), (1, 2)), weights)
        ):
            attrs = {"cost": weight, "payload": payload, "label": f"{u}-{v}"}
            if graph.is_multigraph():
                graph.add_edge(u, v, key=keys[index], **attrs)
            else:
                graph.add_edge(u, v, **attrs)
        if graph.is_multigraph():
            # A real parallel edge exercises keyed selection and key identity.
            worse = max(weights) + 10 if minimum else min(weights) - 10
            graph.add_edge(
                0, 1, key=keys[3], cost=worse, payload=payload, label="parallel"
            )
        graphs.append(graph)
    return graphs[0], graphs[1], payload


def _rows(graph):
    if graph.is_multigraph():
        return list(graph.edges(keys=True, data=True))
    return list(graph.edges(data=True))


def _row_weights(rows):
    return {
        (frozenset((edge[0], edge[1])), edge[2] if len(edge) == 4 else None):
        (edge[-1]["cost"], type(edge[-1]["cost"]))
        for edge in rows
    }


def _assert_exact_rows(actual, expected, payload):
    assert _row_weights(actual) == _row_weights(expected)
    # Graph.size(weight) divides by two and rounds large integer totals.
    assert sum(edge[-1]["cost"] for edge in actual) == sum(
        edge[-1]["cost"] for edge in expected
    )
    assert all(edge[-1]["payload"] is payload for edge in actual)


@pytest.mark.parametrize("domain", ["fraction", "decimal", "large_int"])
@pytest.mark.parametrize("graph_type", ["Graph", "MultiGraph"])
@pytest.mark.parametrize("minimum", [True, False])
@pytest.mark.parametrize("algorithm", ["kruskal", "prim"])
@pytest.mark.parametrize("result_kind", ["tree", "edges"])
def test_spanning_selectors_preserve_exact_weight_comparisons(
    domain, graph_type, minimum, algorithm, result_kind
):
    graph, reference, payload = _graph_pair(
        graph_type, _near_tie_weights(domain, minimum), minimum
    )
    name = f"{'minimum' if minimum else 'maximum'}_spanning_{result_kind}"
    actual = getattr(fnx, name)(graph, weight="cost", algorithm=algorithm)
    expected = getattr(nx, name)(reference, weight="cost", algorithm=algorithm)
    if result_kind == "tree":
        assert type(actual) is getattr(fnx, graph_type)
        assert dict(actual.graph) == dict(expected.graph)
        assert dict(actual.nodes(data=True)) == dict(expected.nodes(data=True))
        actual, expected = _rows(actual), _rows(expected)
    else:
        actual, expected = list(actual), list(expected)
    _assert_exact_rows(actual, expected, payload)


@pytest.mark.parametrize("domain", ["fraction", "decimal", "large_int"])
@pytest.mark.parametrize("graph_type", ["Graph", "MultiGraph"])
@pytest.mark.parametrize("minimum", [True, False])
def test_partition_selector_preserves_exact_weights_and_constraints(
    domain, graph_type, minimum
):
    graph, reference, payload = _graph_pair(
        graph_type, _near_tie_weights(domain, minimum), minimum
    )
    for current in (graph, reference):
        current.add_node(3, label="3")
        current.add_edge(
            2, 3, cost=100, payload=payload, choice=nx.EdgePartition.INCLUDED
        )
        current.add_edge(
            0, 3, cost=-100, payload=payload, choice=nx.EdgePartition.EXCLUDED
        )
    actual = fnx.partition_spanning_tree(
        graph, minimum=minimum, weight="cost", partition="choice"
    )
    expected = nx.partition_spanning_tree(
        reference, minimum=minimum, weight="cost", partition="choice"
    )
    _assert_exact_rows(_rows(actual), _rows(expected), payload)
    assert actual.has_edge(2, 3)
    assert not actual.has_edge(0, 3)
    assert dict(actual.nodes(data=True)) == dict(expected.nodes(data=True))


@pytest.mark.parametrize("domain", ["fraction", "decimal"])
@pytest.mark.parametrize("minimum", [True, False])
def test_iterator_yields_exact_cost_order_and_preserves_attributes(domain, minimum):
    graph, reference, payload = _graph_pair(
        "Graph", _near_tie_weights(domain, minimum), minimum
    )
    actual = list(fnx.SpanningTreeIterator(graph, weight="cost", minimum=minimum))
    expected = list(nx.SpanningTreeIterator(reference, weight="cost", minimum=minimum))
    actual_costs = [sum(data["cost"] for _, _, data in tree.edges(data=True))
                    for tree in actual]
    expected_costs = [sum(data["cost"] for _, _, data in tree.edges(data=True))
                      for tree in expected]
    assert actual_costs == expected_costs == sorted(expected_costs, reverse=not minimum)
    assert len(actual) == 3
    assert len({frozenset(_row_weights(_rows(tree))) for tree in actual}) == 3
    for tree in actual:
        assert tree.graph["payload"] is payload
        assert dict(tree.nodes(data=True)) == dict(graph.nodes(data=True))
        for u, v, data in tree.edges(data=True):
            assert data == graph[u][v]
            assert data is not graph[u][v]
            assert data["payload"] is payload
    actual[0].graph["new"] = True
    actual[0].nodes[0]["label"] = "changed"
    assert "new" not in graph.graph and "new" not in actual[1].graph
    assert graph.nodes[0]["label"] == actual[1].nodes[0]["label"] == "0"


@pytest.mark.parametrize("minimum", [True, False])
def test_iterator_orders_large_integer_totals_without_float_heap_ties(minimum):
    base = 2**53
    sign = 1 if minimum else -1
    weights = [sign * base, sign * (base + 1), sign * (base + 3)]
    graph = fnx.Graph()
    graph.add_weighted_edges_from(
        (u, v, weight)
        for (u, v), weight in zip(((0, 1), (0, 2), (1, 2)), weights)
    )
    trees = list(fnx.SpanningTreeIterator(graph, minimum=minimum))
    costs = [sum(data["weight"] for _, _, data in tree.edges(data=True))
             for tree in trees]
    # The last two candidates have different integer costs but identical
    # Graph.size(weight) float values. The mathematical order is the oracle;
    # NetworkX's iterator currently rounds these heap priorities too.
    expected = sorted(
        (weights[0] + weights[1], weights[0] + weights[2], weights[1] + weights[2]),
        reverse=not minimum,
    )
    assert costs == expected
    assert all(type(cost) is int for cost in costs)


@pytest.mark.parametrize("domain", ["fraction", "decimal", "large_int"])
@pytest.mark.parametrize("minimum", [True, False])
@pytest.mark.parametrize("graph_type", ["Graph", "MultiGraph"])
def test_live_weight_changes_refresh_native_admission(domain, minimum, graph_type):
    initial = (1, 2, 3) if minimum else (-1, -2, -3)
    graph, reference, payload = _graph_pair(graph_type, initial, minimum)
    selectors = [
        (f"{'minimum' if minimum else 'maximum'}_spanning_tree", {"algorithm": "kruskal"}),
        (f"{'minimum' if minimum else 'maximum'}_spanning_tree", {"algorithm": "prim"}),
        (f"{'minimum' if minimum else 'maximum'}_spanning_edges", {"algorithm": "kruskal"}),
        (f"{'minimum' if minimum else 'maximum'}_spanning_edges", {"algorithm": "prim"}),
        ("partition_spanning_tree", {"minimum": minimum}),
    ]
    for name, options in selectors:
        result = getattr(fnx, name)(graph, weight="cost", **options)
        if name.endswith("edges"):
            list(result)
    changed = _near_tie_weights(domain, minimum)
    for current in (graph, reference):
        for (u, v), weight in zip(((0, 1), (0, 2), (1, 2)), changed):
            attrs = current[u][v]
            if current.is_multigraph():
                attrs = next(iter(attrs.values()))
            attrs["cost"] = weight
        if current.is_multigraph():
            parallel = list(current[0][1].values())[1]
            parallel["cost"] = max(changed) + 10 if minimum else min(changed) - 10
    for name, options in selectors:
        actual = getattr(fnx, name)(graph, weight="cost", **options)
        expected = getattr(nx, name)(reference, weight="cost", **options)
        if name.endswith("edges"):
            actual, expected = list(actual), list(expected)
        else:
            actual, expected = _rows(actual), _rows(expected)
        _assert_exact_rows(actual, expected, payload)


@pytest.mark.parametrize("weights", [(-3, 2, 4), (-3.5, 2.25, 4.0), (False, True, True)])
def test_ordinary_weights_keep_native_selectors(monkeypatch, weights):
    graph, _, _ = _graph_pair("Graph", weights)
    cases = [
        ("minimum_spanning_tree", {}, fnx, "_raw_minimum_spanning_tree"),
        ("maximum_spanning_tree", {}, fnx, "_raw_maximum_spanning_tree"),
        ("minimum_spanning_edges", {}, fnx, "_raw_minimum_spanning_edges"),
        ("maximum_spanning_edges", {}, fnx._fnx, "maximum_spanning_edges"),
        ("minimum_spanning_edges", {"algorithm": "prim"}, fnx, "_raw_prim_spanning_edges"),
        ("maximum_spanning_edges", {"algorithm": "prim"}, fnx, "_raw_prim_spanning_edges"),
        ("partition_spanning_tree", {}, fnx, "_raw_partition_spanning_tree"),
    ]
    for name, options, module, raw_name in cases:
        calls = []
        raw = getattr(module, raw_name)

        def counted(*args, **kwargs):
            calls.append(True)
            return raw(*args, **kwargs)

        with monkeypatch.context() as patch:
            patch.setattr(module, raw_name, counted)
            result = getattr(fnx, name)(graph, weight="cost", **options)
            if name.endswith("edges"):
                list(result)
            assert calls, (name, options, weights)


@pytest.mark.parametrize("domain", ["fraction", "large_int"])
def test_missing_native_scan_keeps_exact_selection(monkeypatch, domain):
    graph, reference, payload = _graph_pair("Graph", _near_tie_weights(domain, True))
    monkeypatch.setattr(fnx, "_native_check_dijkstra_weights_fast", None)
    actual = fnx.minimum_spanning_tree(graph, weight="cost")
    expected = nx.minimum_spanning_tree(reference, weight="cost")
    _assert_exact_rows(_rows(actual), _rows(expected), payload)


@pytest.mark.parametrize("algorithm", ["kruskal", "prim", "boruvka", "partition"])
@pytest.mark.parametrize("value,ignore_nan", [
    pytest.param("1", False, id="string"),
    pytest.param(Decimal("NaN"), False, id="decimal_nan_rejected"),
    pytest.param(Decimal("NaN"), True, id="decimal_nan_ignored"),
])
def test_fallback_weight_validation_matches_networkx(algorithm, value, ignore_nan):
    def select(library):
        graph = library.Graph()
        graph.add_edge(0, 1, cost=value)
        if not isinstance(value, str):
            graph.add_edge(1, 2, cost=2)
        if algorithm == "partition":
            tree = library.partition_spanning_tree(
                graph, weight="cost", ignore_nan=ignore_nan
            )
            return list(tree.edges(data=True))
        return list(library.minimum_spanning_edges(
            graph, weight="cost", algorithm=algorithm, ignore_nan=ignore_nan
        ))

    if ignore_nan:
        assert select(fnx) == select(nx) == [(1, 2, {"cost": 2})]
    else:
        error = TypeError if isinstance(value, str) else ValueError
        with pytest.raises(error):
            select(nx)
        with pytest.raises(error):
            select(fnx)
