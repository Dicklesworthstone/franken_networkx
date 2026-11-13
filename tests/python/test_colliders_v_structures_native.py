"""br-r37-c1-n23aj: regression tests for native colliders + v_structures."""

from __future__ import annotations

import pytest

import franken_networkx as fnx

try:
    import networkx as nx

    HAS_NX = True
except ImportError:
    HAS_NX = False


needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


def _build(cls, edges):
    g = cls()
    for u, v in edges:
        g.add_edge(u, v)
    return g


def _normalize_triples(triples):
    """Normalize (p1, collider, p2) triples by sorting the parent pair so
    fnx vs nx node-iteration order doesn't affect equality."""
    return {(min(p1, p2), c, max(p1, p2)) for p1, c, p2 in triples}


@needs_nx
def test_colliders_matches_nx_on_docstring_example():
    # br-r37-c1-ax3ix: nx yields (p1, c, p2) triples where the parent
    # order depends on graph node-iteration order. fnx and nx have
    # the same node-iteration semantics (insertion-order) but the
    # node-creation timing in _build differs, so the parent pair can
    # come out swapped. Normalize the unordered parent pair before
    # comparing.
    edges = [(1, 2), (0, 4), (3, 1), (2, 4), (0, 5), (4, 5), (1, 5)]
    fg = _build(fnx.DiGraph, edges)
    ng = _build(nx.DiGraph, edges)
    assert _normalize_triples(fnx.algorithms.dag.colliders(fg)) == \
           _normalize_triples(nx.algorithms.dag.colliders(ng))


@needs_nx
def test_v_structures_matches_nx_on_docstring_example():
    # br-r37-c1-ax3ix: same parity contract as colliders.
    edges = [(1, 2), (0, 4), (3, 1), (2, 4), (0, 5), (4, 5), (1, 5)]
    fg = _build(fnx.DiGraph, edges)
    ng = _build(nx.DiGraph, edges)
    assert _normalize_triples(fnx.algorithms.dag.v_structures(fg)) == \
           _normalize_triples(nx.algorithms.dag.v_structures(ng))


def test_colliders_empty_dag():
    g = fnx.DiGraph()
    g.add_edge(0, 1)
    assert list(fnx.algorithms.dag.colliders(g)) == []


def test_colliders_two_parents():
    g = fnx.DiGraph()
    g.add_edge(0, 2)
    g.add_edge(1, 2)
    assert list(fnx.algorithms.dag.colliders(g)) == [(0, 2, 1)]


def test_v_structures_unmarried_only():
    g = fnx.DiGraph()
    g.add_edge(0, 2)
    g.add_edge(1, 2)
    # Without edge between 0 and 1, this is a v-structure.
    assert list(fnx.algorithms.dag.v_structures(g)) == [(0, 2, 1)]
    # Adding 0->1 makes them "married" — no longer a v-structure.
    g.add_edge(0, 1)
    assert list(fnx.algorithms.dag.v_structures(g)) == []


@pytest.mark.parametrize("cls", [fnx.Graph, fnx.MultiGraph])
def test_colliders_rejects_undirected(cls):
    g = cls()
    g.add_edge(0, 1)
    with pytest.raises(fnx.NetworkXNotImplemented):
        fnx.algorithms.dag.colliders(g)


@pytest.mark.parametrize("cls", [fnx.Graph, fnx.MultiGraph])
def test_v_structures_rejects_undirected(cls):
    g = cls()
    g.add_edge(0, 1)
    with pytest.raises(fnx.NetworkXNotImplemented):
        fnx.algorithms.dag.v_structures(g)


@needs_nx
def test_colliders_allows_cyclic_graphs():
    # nx docs explicitly note this — the algorithm works on cycles.
    edges = [(0, 1), (1, 0), (0, 2), (1, 2)]
    fg = _build(fnx.DiGraph, edges)
    ng = _build(nx.DiGraph, edges)
    assert list(fnx.algorithms.dag.colliders(fg)) == list(nx.algorithms.dag.colliders(ng))


def _live_graph(module, cls_name, layout, edges):
    root = getattr(module, cls_name)()
    root.add_nodes_from(range(7))
    root.add_edges_from((v, u) if layout == "reverse" else (u, v) for u, v in edges)
    if layout == "subgraph":
        graph = root.subgraph(range(7))
    elif layout == "reverse":
        graph = root.reverse(copy=False)
    else:
        graph = root
    return root, graph


def _mutate_edge(root, layout, method, u, v):
    getattr(root, method)(*(v, u) if layout == "reverse" else (u, v))


@needs_nx
@pytest.mark.parametrize("name", ["colliders", "v_structures"])
@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("layout", ["concrete", "subgraph", "reverse"])
def test_collider_iteration_reads_graph_on_first_next(name, cls_name, layout):
    results = []
    for module in (fnx, nx):
        root, graph = _live_graph(module, cls_name, layout, [(0, 2)])
        iterator = getattr(module.algorithms.dag, name)(graph)
        _mutate_edge(root, layout, "add_edge", 1, 2)
        results.append(list(iterator))
    assert results[0] == results[1] == [(0, 2, 1)]


@needs_nx
@pytest.mark.parametrize("name", ["colliders", "v_structures"])
@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("layout", ["concrete", "subgraph", "reverse"])
def test_collider_iteration_keeps_current_pairs_but_reads_later_rows(name, cls_name, layout):
    edges = [(0, 3), (1, 3), (2, 3), (0, 5), (1, 5), (2, 6)]
    results = []
    for module in (fnx, nx):
        root, graph = _live_graph(module, cls_name, layout, edges)
        iterator = getattr(module.algorithms.dag, name)(graph)
        prefix = [next(iterator)]
        _mutate_edge(root, layout, "remove_edge", 2, 3)
        _mutate_edge(root, layout, "remove_edge", 1, 5)
        _mutate_edge(root, layout, "add_edge", 1, 6)
        results.append(prefix + list(iterator))
    assert results[0] == results[1] == [
        (0, 3, 1), (0, 3, 2), (1, 3, 2), (2, 6, 1)
    ]


@needs_nx
@pytest.mark.parametrize("name", ["colliders", "v_structures"])
@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("provider_kind", ["instance", "class"])
def test_collider_iteration_calls_predecessor_providers(
    name, cls_name, provider_kind, monkeypatch
):
    results = []
    for module in (fnx, nx):
        cls = getattr(module, cls_name)
        graph = cls()
        graph.add_nodes_from(range(3))
        graph.add_edge(0, 2)
        original = cls.predecessors
        calls = []

        def predecessors(self, node):
            calls.append(node)
            if node == 0:
                self.add_edge(1, 2)
            return original(self, node)

        with monkeypatch.context() as patch:
            if provider_kind == "instance":
                patch.setattr(graph, "predecessors", lambda node: predecessors(graph, node))
            else:
                patch.setattr(cls, "predecessors", predecessors)
            iterator = getattr(module.algorithms.dag, name)(graph)
            assert calls == []
            results.append((list(iterator), calls[:]))
    assert results[0] == results[1] == ([(0, 2, 1)], [0, 1, 2])


@needs_nx
@pytest.mark.parametrize("name", ["colliders", "v_structures"])
@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
def test_collider_iteration_notices_replaced_predecessor_provider(name, cls_name):
    results = []
    for module in (fnx, nx):
        _, graph = _live_graph(
            module, cls_name, "concrete", [(0, 3), (1, 3), (0, 5), (1, 5)]
        )
        iterator = getattr(module.algorithms.dag, name)(graph)
        prefix = [next(iterator)]
        original = graph.predecessors
        calls = []

        def predecessors(node):
            calls.append(node)
            return reversed(list(original(node)))

        graph.predecessors = predecessors
        results.append((prefix + list(iterator), calls))
    assert results[0] == results[1] == ([(0, 3, 1), (1, 5, 0)], [4, 5, 6])


@needs_nx
@pytest.mark.parametrize("name", ["colliders", "v_structures"])
@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
def test_collider_iteration_pins_public_node_iterator(name, cls_name):
    results = []
    for module in (fnx, nx):
        _, graph = _live_graph(
            module, cls_name, "concrete", [(0, 3), (1, 3), (0, 5), (1, 5)]
        )
        graph.nodes = [5, 3]
        iterator = getattr(module.algorithms.dag, name)(graph)
        prefix = [next(iterator)]
        graph.nodes = []
        results.append(prefix + list(iterator))
    assert results[0] == results[1] == [(0, 5, 1), (0, 3, 1)]


@needs_nx
@pytest.mark.parametrize("name", ["colliders", "v_structures"])
@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
def test_collider_iteration_preserves_node_hash_mutation(name, cls_name):
    class Node:
        armed = False

        def __hash__(self):
            if self.armed:
                self.armed = False
                self.graph.add_edge(1, 6)
            return 9107

    results = []
    for module in (fnx, nx):
        graph = getattr(module, cls_name)()
        node = Node()
        node.graph = graph
        graph.add_nodes_from([0, 1, 2, 3, node, 6])
        graph.add_edges_from([(0, 3), (1, 3), (2, 6)])
        iterator = getattr(module.algorithms.dag, name)(graph)
        # The node iterator is already open when this hook is armed. This
        # isolates live predecessor lookups from native node-mirror creation.
        prefix = [next(iterator)]
        node.armed = True
        results.append(prefix + list(iterator))
    assert results[0] == results[1] == [(0, 3, 1), (2, 6, 1)]


@needs_nx
@pytest.mark.parametrize("name", ["colliders", "v_structures"])
@pytest.mark.parametrize("provider", ["graph", "node"])
def test_collider_admission_does_not_compare_or_hash_user_types(name, provider):
    class Meta(type):
        armed = False

        def __eq__(cls, other):
            if Meta.armed:
                raise AssertionError("algorithm compared a caller-owned type")
            return type.__eq__(cls, other)

        def __hash__(cls):
            if Meta.armed:
                raise AssertionError("algorithm hashed a caller-owned type")
            return type.__hash__(cls)

    class Node(metaclass=Meta):
        pass

    results = []
    for module in (fnx, nx):
        cls = Meta("ProviderGraph", (module.DiGraph,), {}) if provider == "graph" else module.DiGraph
        graph = cls()
        if provider == "node":
            graph.add_node(Node())
        graph.add_edges_from([(0, 2), (1, 2)])
        Meta.armed = True
        try:
            results.append(list(getattr(module.algorithms.dag, name)(graph)))
        finally:
            Meta.armed = False
    assert results[0] == results[1] == [(0, 2, 1)]


def _remaining_or_error(iterator):
    values = []
    try:
        values.extend(iterator)
    except Exception as error:
        return values, (type(error).__name__, str(error))
    return values, None


@needs_nx
@pytest.mark.parametrize("name", ["colliders", "v_structures"])
@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("mutation", ["add", "replace"])
def test_collider_iteration_preserves_node_dictionary_errors(name, cls_name, mutation):
    results = []
    for module in (fnx, nx):
        _, graph = _live_graph(
            module, cls_name, "concrete", [(0, 3), (1, 3), (2, 3)]
        )
        iterator = getattr(module.algorithms.dag, name)(graph)
        assert next(iterator) == (0, 3, 1)
        if mutation == "replace":
            graph.remove_node(0)
        graph.add_node(7)
        results.append(_remaining_or_error(iterator))
    assert results[0] == results[1]
    assert results[1][1][0] == "RuntimeError"


@needs_nx
@pytest.mark.parametrize("name", ["colliders", "v_structures"])
@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
def test_collider_iteration_retains_plain_native_batch(name, cls_name, monkeypatch):
    dag = fnx.algorithms.dag
    original = dag._bulk_predecessor_rows
    snapshots = []

    def record(*args):
        snapshot = original(*args)
        snapshots.append(snapshot)
        return snapshot

    monkeypatch.setattr(dag, "_bulk_predecessor_rows", record)
    edges = [(0, 3), (1, 3), (2, 3), (0, 5), (1, 5)]
    _, graph = _live_graph(fnx, cls_name, "concrete", edges)
    _, oracle = _live_graph(nx, cls_name, "concrete", edges)
    iterator = getattr(dag, name)(graph)
    assert snapshots == []
    assert list(iterator) == list(getattr(nx.algorithms.dag, name)(oracle))
    assert len(snapshots) == 1
    assert snapshots[0] is not None
    assert len(snapshots[0][0]) == 7
