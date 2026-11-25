"""Parity for ``node_connected_component`` missing-node exception.

networkx's ``node_connected_component`` runs a plain BFS that indexes
``G._adj[n]``, so a missing (hashable) node surfaces as a bare
``KeyError(n)``. fnx previously raised ``NodeNotFound`` from the native
binding. This locks fnx to nx's exception type and args. The unhashable
path (TypeError) and valid queries are unaffected. br-r37-c1-eun8y
"""

from __future__ import annotations

import pytest
import networkx as nx
import franken_networkx as fnx


def _graphs():
    return fnx.Graph([(0, 1), (1, 2), (5, 6)]), nx.Graph([(0, 1), (1, 2), (5, 6)])


@pytest.mark.parametrize("missing", ["x", 99, ("a", "b")])
def test_missing_node_raises_keyerror_like_networkx(missing):
    fg, ng = _graphs()
    with pytest.raises(KeyError) as fnx_exc:
        fnx.node_connected_component(fg, missing)
    with pytest.raises(KeyError) as nx_exc:
        nx.node_connected_component(ng, missing)
    assert fnx_exc.value.args == nx_exc.value.args == (missing,)


@pytest.mark.parametrize("unhashable", [[1, 2], {1: 2}])
def test_unhashable_node_raises_typeerror_like_networkx(unhashable):
    fg, ng = _graphs()
    with pytest.raises(TypeError):
        fnx.node_connected_component(fg, unhashable)
    with pytest.raises(TypeError):
        nx.node_connected_component(ng, unhashable)


@pytest.mark.parametrize("node", [0, "missing"])
def test_directed_input_rejects_before_node_lookup(node):
    fg = fnx.DiGraph([(0, 1)])
    ng = nx.DiGraph([(0, 1)])

    with pytest.raises(nx.NetworkXNotImplemented) as fnx_exc:
        fnx.node_connected_component(fg, node)
    with pytest.raises(nx.NetworkXNotImplemented) as nx_exc:
        nx.node_connected_component(ng, node)
    assert (
        str(fnx_exc.value)
        == str(nx_exc.value)
        == "not implemented for directed type"
    )


def test_valid_query_matches_networkx():
    fg, ng = _graphs()
    assert fnx.node_connected_component(fg, 0) == nx.node_connected_component(ng, 0)
    assert fnx.node_connected_component(fg, 5) == nx.node_connected_component(ng, 5)


_LIVE_COMPONENT_ROUTES = ["native", "networkx", "backend", "cached-backend"]


def _live_component_call(graph, source, route, reference=False):
    if reference:
        return nx.node_connected_component(graph, source)
    if route in {"backend", "cached-backend"}:
        return nx.node_connected_component(graph, source, backend="franken_networkx")
    return fnx.node_connected_component(graph, source)


def _prewarm_component(graph, route, reference=False):
    if route == "cached-backend" and not reference:
        nx.relabel_nodes(graph, {}, backend="franken_networkx")
        assert graph.__networkx_cache__.get("backends", {}).get("franken_networkx")


@pytest.mark.parametrize("route", _LIVE_COMPONENT_ROUTES)
@pytest.mark.parametrize("graph_class", ["Graph", "MultiGraph"])
def test_node_component_reads_only_reached_live_rows(route, graph_class):
    def run(reference):
        library = fnx if route == "native" and not reference else nx
        graph = getattr(library, graph_class)()
        graph.add_nodes_from([0, 1, 2, 100, 101])
        graph.add_edges_from([(0, 1), (100, 101)])
        logical = getattr(nx, graph_class)(graph.edges())
        logical.add_nodes_from([0, 1, 2, 100, 101])
        _prewarm_component(graph, route, reference)
        calls = []

        class Rows(dict):
            def __getitem__(self, node):
                calls.append(node)
                if node >= 100:
                    raise AssertionError("visited an unrelated component")
                if node == 1:
                    attrs = {0: {}} if graph_class == "MultiGraph" else {}
                    dict.__getitem__(self, 1)[2] = attrs
                    dict.__getitem__(self, 2)[1] = attrs
                return dict.__getitem__(self, node)

            def items(self):
                raise AssertionError("materialized all adjacency rows")

        graph._node = logical._node
        graph._adj = Rows(logical._adj)
        result = _live_component_call(graph, 0, route, reference)
        if route == "cached-backend" and not reference:
            assert not graph.__networkx_cache__
        return result, calls

    assert run(False) == run(True) == ({0, 1, 2}, [0, 1, 2])


@pytest.mark.parametrize("route", _LIVE_COMPONENT_ROUTES)
@pytest.mark.parametrize("graph_class", ["Graph", "MultiGraph"])
def test_node_component_keeps_the_equal_source_object(route, graph_class):
    library = fnx if route == "native" else nx
    graph = getattr(library, graph_class)([(1, 2), (2, 3)])
    _prewarm_component(graph, route)
    source = float(1)
    result = _live_component_call(graph, source, route)
    assert result == {1, 2, 3}
    assert any(node is source for node in result)


@pytest.mark.parametrize("graph_class", ["Graph", "MultiGraph"])
def test_node_component_keeps_equal_neighbor_aliases(graph_class):
    class Alias(int):
        pass

    alias = Alias(1)
    graph = getattr(fnx, graph_class)()
    graph.add_nodes_from([0, 1])
    graph.add_edge(0, alias)
    result = fnx.node_connected_component(graph, 0)
    assert result == {0, 1}
    assert any(node is alias for node in result)


@pytest.mark.parametrize("route", _LIVE_COMPONENT_ROUTES)
def test_node_component_preserves_row_provider_exception(route):
    library = fnx if route == "native" else nx
    graph = library.Graph([(0, 1)])
    _prewarm_component(graph, route)
    error = nx.NetworkXNotImplemented("row provider failed")
    calls = []

    class Rows(dict):
        def __getitem__(self, node):
            calls.append(node)
            raise error

    graph._adj = Rows({0: {1: {}}, 1: {0: {}}})
    with pytest.raises(nx.NetworkXNotImplemented) as caught:
        _live_component_call(graph, 0, route)
    assert caught.value is error
    assert calls == [0]


@pytest.mark.parametrize("graph_class", ["Graph", "MultiGraph"])
def test_plain_node_component_retains_native_kernel(monkeypatch, graph_class):
    namespace = fnx.node_connected_component.__globals__
    raw = namespace["_raw_node_connected_component"]
    calls = []

    def native(graph, source):
        calls.append((graph, source))
        return raw(graph, source)

    monkeypatch.setitem(namespace, "_raw_node_connected_component", native)
    graph = getattr(fnx, graph_class)([(0, 1), (1, 2)])
    assert fnx.node_connected_component(graph, 0) == {0, 1, 2}
    assert fnx.node_connected_component(graph, 1) == {0, 1, 2}
    assert calls == [(graph, 0), (graph, 1)]
