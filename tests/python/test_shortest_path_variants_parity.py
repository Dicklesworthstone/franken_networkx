"""Phase B certification: shortest-path variants (astar, bidirectional,
johnson, floyd_warshall, all_pairs_bellman_ford) and disjoint paths.
Zero divergences.
"""
import random

import networkx as nx
import pytest

import franken_networkx as fnx


def _mkw(mod, directed=False):
    R = random.Random(103)
    we = [(u, v, R.randrange(1, 9)) for u, v in ((R.randrange(12), R.randrange(12)) for _ in range(40)) if u != v]
    g = (mod.DiGraph if directed else mod.Graph)()
    for u, v, w in we:
        g.add_edge(u, v, weight=w)
    return g


def _P(p):
    return [repr(n) for n in p]


def test_astar_and_bidirectional():
    gf, gn = _mkw(fnx), _mkw(nx)
    assert _P(fnx.astar_path(gf, 0, 9)) == _P(nx.astar_path(gn, 0, 9))
    assert fnx.astar_path_length(gf, 0, 9) == nx.astar_path_length(gn, 0, 9)
    df, pf = fnx.bidirectional_dijkstra(gf, 0, 9)
    dn, pn = nx.bidirectional_dijkstra(gn, 0, 9)
    assert (df, _P(pf)) == (dn, _P(pn))
    assert _P(fnx.bidirectional_shortest_path(gf, 0, 9)) == _P(nx.bidirectional_shortest_path(gn, 0, 9))


def test_all_pairs_path_lengths():
    gf, gn = _mkw(fnx), _mkw(nx)
    assert {repr(s): {repr(t): _P(p) for t, p in d.items()} for s, d in fnx.johnson(gf).items()} == {
        repr(s): {repr(t): _P(p) for t, p in d.items()} for s, d in nx.johnson(gn).items()
    }
    assert {repr(s): {repr(t): l for t, l in d.items()} for s, d in fnx.floyd_warshall(gf).items()} == {
        repr(s): {repr(t): l for t, l in d.items()} for s, d in nx.floyd_warshall(gn).items()
    }
    assert {repr(s): {repr(t): l for t, l in d.items()} for s, d in fnx.all_pairs_bellman_ford_path_length(gf)} == {
        repr(s): {repr(t): l for t, l in d.items()} for s, d in nx.all_pairs_bellman_ford_path_length(gn)
    }


def test_disjoint_paths():
    df, dn = _mkw(fnx, True), _mkw(nx, True)
    assert len(list(nx.node_disjoint_paths(df, 0, 9))) == len(list(nx.node_disjoint_paths(dn, 0, 9)))
    assert len(list(nx.edge_disjoint_paths(df, 0, 9))) == len(list(nx.edge_disjoint_paths(dn, 0, 9)))
    gf, gn = _mkw(fnx), _mkw(nx)
    assert fnx.has_path(gf, 0, 9) == nx.has_path(gn, 0, 9)
    assert fnx.shortest_path_length(gf, 0, 9, weight="weight") == nx.shortest_path_length(
        gn, 0, 9, weight="weight"
    )


_WEIGHTED_ROUTE_QUERIES = [
    ("multi_source_dijkstra", (["r", "s"],), {}),
    ("multi_source_dijkstra", (["r", "s"],), {"target": "t"}),
    ("multi_source_dijkstra", (["r", "s"],), {"cutoff": 1}),
    ("multi_source_dijkstra_path", (["r", "s"],), {}),
    ("multi_source_dijkstra_path_length", (["r", "s"],), {"cutoff": 3}),
    ("dijkstra_predecessor_and_distance", ("s",), {}),
    ("dijkstra_predecessor_and_distance", ("s",), {"cutoff": 1}),
    ("bidirectional_dijkstra", ("s", "t"), {}),
]
_WEIGHTED_ROUTE_NAMES = [
    "multi_source_dijkstra", "multi_source_dijkstra_path",
    "multi_source_dijkstra_path_length", "dijkstra_predecessor_and_distance",
    "bidirectional_dijkstra",
]
_MULTISOURCE_NAMES = _WEIGHTED_ROUTE_NAMES[:3]
_GRAPH_CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _ordered_weighted_value(value):
    if isinstance(value, dict):
        return "dict", [
            (_ordered_weighted_value(key), _ordered_weighted_value(item))
            for key, item in value.items()
        ]
    if isinstance(value, (list, tuple)):
        return type(value).__name__, [_ordered_weighted_value(item) for item in value]
    return type(value).__name__, value


def _weighted_outcome(call):
    try:
        return "return", _ordered_weighted_value(call())
    except Exception as exc:  # noqa: BLE001 - public error parity
        return "raise", type(exc).__name__, str(exc)


def _weighted_route_graph(library, graph_class):
    graph = getattr(library, graph_class)()
    graph.add_nodes_from(["s", "r", "a", "b", "t", "isolated"])
    graph.add_weighted_edges_from([
        ("s", "a", 1), ("s", "b", 1.0), ("r", "b", 1),
        ("a", "t", 2), ("b", "t", 2), ("t", "t", 0),
    ])
    if graph.is_multigraph():
        graph.add_edge("s", "a", key="parallel", weight=8)
    return graph


def _prewarm_weighted_backend(graph):
    nx.shortest_path(graph, "s", "t", weight="weight", backend="franken_networkx")


@pytest.mark.parametrize("name,args,options", _WEIGHTED_ROUTE_QUERIES)
@pytest.mark.parametrize("graph_class", _GRAPH_CLASSES)
@pytest.mark.parametrize("prewarmed", [False, True])
def test_weighted_query_backend_family_preserves_order_and_distance_types(
    name, args, options, graph_class, prewarmed
):
    graph = _weighted_route_graph(nx, graph_class)
    expected = getattr(nx, name)(graph, *args, backend="networkx", **options)
    if prewarmed:
        _prewarm_weighted_backend(graph)
    actual = getattr(nx, name)(graph, *args, backend="franken_networkx", **options)
    assert _ordered_weighted_value(actual) == _ordered_weighted_value(expected)


@pytest.mark.parametrize("name", _WEIGHTED_ROUTE_NAMES)
@pytest.mark.parametrize("graph_class", _GRAPH_CLASSES)
@pytest.mark.parametrize("prewarmed", [False, True])
@pytest.mark.parametrize("filtered", [False, True])
def test_weighted_query_backend_family_keeps_live_hidden_edge_callbacks(
    name, graph_class, prewarmed, filtered
):
    def run(backend):
        root = _weighted_route_graph(nx, graph_class)
        root.add_edge("s", "t", weight=0, hidden=True)
        if filtered:
            root.add_weighted_edges_from([("s", "outside", 0), ("outside", "t", 0)])
            graph = root.subgraph([node for node in root if node != "outside"])
        else:
            graph = root
        if prewarmed and backend == "franken_networkx":
            _prewarm_weighted_backend(graph)
        calls = []

        def weight(u, v, data):
            calls.append((u, v))
            assert graph.number_of_edges() > 0
            if graph.is_multigraph():
                for key, attrs in data.items():
                    assert attrs is graph[u][v][key]
                edge_attrs = list(data.values())
            else:
                assert data is graph[u][v]
                edge_attrs = [data]
            for attrs in edge_attrs:
                attrs["visited"] = True
            if (u, v) == ("s", "a"):
                later = graph["a"]["t"]
                shortcut = graph["s"]["t"]
                if graph.is_multigraph():
                    later = later[0]
                    shortcut = shortcut[0]
                later["weight"] = 1
                shortcut["weight"] = 50
            visible = [attrs["weight"] for attrs in edge_attrs if not attrs.get("hidden")]
            return min(visible) if visible else None

        if name in _MULTISOURCE_NAMES:
            args = (["s"],)
        else:
            args = ("s", "t") if name == "bidirectional_dijkstra" else ("s",)
        result = getattr(nx, name)(graph, *args, weight=weight, backend=backend)
        # The callback changed weights without graph mutators. A following
        # ordinary query must not reuse the prewarmed zero-cost shortcut.
        following = nx.shortest_path_length(
            graph, "s", "t", weight="weight", backend=backend
        )
        assert following == 2
        edge_options = {"keys": True} if root.is_multigraph() else {}
        return (
            _ordered_weighted_value(result), calls, following,
            list(root.edges(data=True, **edge_options)),
        )

    assert run("franken_networkx") == run("networkx")


@pytest.mark.parametrize("name", _MULTISOURCE_NAMES)
@pytest.mark.parametrize("graph_class", _GRAPH_CLASSES)
@pytest.mark.parametrize("route", ["native-input", "networkx-input", "backend", "warm-backend"])
@pytest.mark.parametrize("one_shot", [False, True])
@pytest.mark.parametrize("filtered", [False, True])
def test_multisource_queries_observe_source_iteration_mutations(
    name, graph_class, route, one_shot, filtered
):
    def run(reference):
        library = nx if reference or route != "native-input" else fnx
        root = getattr(library, graph_class)()
        root.add_edge("s", "t", weight=9)
        root.add_node("a")
        graph = (
            library.subgraph_view(root, filter_node=lambda node: node != "outside")
            if filtered else root
        )
        if not reference and route == "warm-backend":
            _prewarm_weighted_backend(graph)
        calls = []

        class Sources:
            def __bool__(self):
                calls.append("truth")
                return True

            def __iter__(self):
                calls.append("sources")
                root.add_weighted_edges_from([("new", "a", 1), ("a", "t", 1)])
                yield "new"

        sources = iter(Sources()) if one_shot else Sources()
        if reference:
            query = lambda: getattr(nx, name)(graph, sources, backend="networkx")
        elif route in ("backend", "warm-backend"):
            query = lambda: getattr(nx, name)(graph, sources, backend="franken_networkx")
        else:
            query = lambda: getattr(fnx, name)(graph, sources)
        outcome = _weighted_outcome(query)
        edge_options = {"keys": True} if root.is_multigraph() else {}
        return outcome, calls, list(root.nodes()), list(root.edges(data=True, **edge_options))

    expected = run(True)
    assert expected[0][0] == "return"
    assert run(False) == expected


@pytest.mark.parametrize("name", _MULTISOURCE_NAMES)
@pytest.mark.parametrize("ending", ["missing-source", "iterator-error", "exhausted"])
@pytest.mark.parametrize("route", ["direct", "backend", "warm-backend"])
def test_multisource_source_generator_errors_precede_target_shortcuts(name, ending, route):
    def run(reference):
        graph = nx.DiGraph()
        graph.add_edge("s", "t", weight=1)
        if not reference and route == "warm-backend":
            _prewarm_weighted_backend(graph)
        events = []

        def sources():
            events.append("source")
            yield "s"
            if ending == "missing-source":
                events.append("missing")
                yield "missing"
            elif ending == "iterator-error":
                events.append("error")
                raise LookupError("source iteration failed")
            events.append("exhausted")

        options = {"target": "s"} if name == "multi_source_dijkstra" else {}
        if reference:
            call = lambda: getattr(nx, name)(graph, sources(), backend="networkx", **options)
        elif route == "direct":
            call = lambda: getattr(fnx, name)(graph, sources(), **options)
        else:
            call = lambda: getattr(nx, name)(
                graph, sources(), backend="franken_networkx", **options
            )
        return _weighted_outcome(call), events

    assert run(False) == run(True)


@pytest.mark.parametrize("name", _MULTISOURCE_NAMES)
@pytest.mark.parametrize("graph_class", _GRAPH_CLASSES)
@pytest.mark.parametrize("source_type", [list, tuple, set, frozenset, dict, range])
def test_multisource_plain_collections_retain_native_routes(
    monkeypatch, name, graph_class, source_type
):
    graph = getattr(fnx, graph_class)()
    graph.add_weighted_edges_from([(0, 2, 1), (1, 2, 1), (2, 3, 2)])
    reference = getattr(nx, graph_class)()
    reference.add_weighted_edges_from([(0, 2, 1), (1, 2, 1), (2, 3, 2)])
    if source_type is range:
        sources = range(2)
    elif source_type is dict:
        sources = {0: None, 1: None}
    else:
        sources = source_type([0, 1])
    expected = getattr(nx, name)(reference, sources, backend="networkx")

    def left_native(*args, **kwargs):
        raise AssertionError("ordinary source collection left its native route")

    namespace = fnx.multi_source_dijkstra.__globals__
    monkeypatch.setitem(namespace, "_multi_source_dijkstra_inproc", left_native)
    monkeypatch.setitem(namespace, "_dijkstra_multisource_inproc", left_native)
    actual = getattr(fnx, name)(graph, sources)
    assert _ordered_weighted_value(actual) == _ordered_weighted_value(expected)


def _compound_builtin_label(kind, value):
    if kind == "tuple":
        return (value, "node")
    if kind == "frozenset":
        return frozenset((value, "node"))
    return ((value, "node"), frozenset((b"layer", None, 2j)))


@pytest.mark.parametrize("name", _MULTISOURCE_NAMES)
@pytest.mark.parametrize("graph_class", _GRAPH_CLASSES)
@pytest.mark.parametrize("kind", ["tuple", "frozenset", "nested"])
@pytest.mark.parametrize("route", ["native-input", "networkx-input", "backend"])
def test_multisource_compound_builtin_labels_preserve_typed_routes(
    monkeypatch, name, graph_class, kind, route
):
    labels = [_compound_builtin_label(kind, value) for value in range(6)]
    reference = getattr(nx, graph_class)()
    reference.add_nodes_from(labels)
    reference.add_weighted_edges_from([
        (labels[0], labels[2], 1), (labels[0], labels[3], 1.0),
        (labels[1], labels[3], 1), (labels[2], labels[4], 2),
        (labels[3], labels[4], 2), (labels[4], labels[4], 0),
    ])
    if reference.is_multigraph():
        reference.add_edge(labels[0], labels[2], key="parallel", weight=8)
    library = fnx if route == "native-input" else nx
    graph = getattr(library, graph_class)(reference)
    for reader in ("nodes", "edges", "adj"):
        getattr(graph, reader)
    # Equal labels supplied by the caller remain the roots of returned paths.
    sources = [_compound_builtin_label(kind, value) for value in (1, 0)]
    namespace = fnx.multi_source_dijkstra.__globals__
    calls = []
    uses_native = route == "native-input" and graph_class in ("Graph", "DiGraph")
    if name == "multi_source_dijkstra_path_length":
        native = namespace["_fnx"].multi_source_dijkstra_path_length
    else:
        native = namespace["_raw_multi_source_dijkstra"]

    def record_native(*args, **kwargs):
        calls.append(None)
        return native(*args, **kwargs)

    def left_native(*args, **kwargs):
        raise AssertionError("builtin compound labels left the native search")

    if uses_native:
        monkeypatch.setitem(namespace, "_multi_source_dijkstra_inproc", left_native)
        monkeypatch.setitem(namespace, "_dijkstra_multisource_inproc", left_native)
    if name == "multi_source_dijkstra_path_length":
        monkeypatch.setattr(namespace["_fnx"], name, record_native)
    else:
        monkeypatch.setitem(namespace, "_raw_multi_source_dijkstra", record_native)

    for weight in (2, 0.25):
        for item in (graph, reference):
            if route == "backend":
                # NetworkX invalidates cached backend conversions through
                # graph mutators, not direct edits of its attribute dicts.
                keys = {"key": 0} if item.is_multigraph() else {}
                item.add_edge(labels[2], labels[4], weight=weight, **keys)
                continue
            edge = item[labels[2]][labels[4]]
            if item.is_multigraph():
                edge = edge[0]
            edge["weight"] = weight
        expected = getattr(nx, name)(reference, sources, backend="networkx")
        actual = (
            getattr(nx, name)(graph, sources, backend="franken_networkx")
            if route == "backend" else getattr(fnx, name)(graph, sources)
        )
        assert _ordered_weighted_value(actual) == _ordered_weighted_value(expected)
        if name != "multi_source_dijkstra_path_length":
            paths = actual[1] if name == "multi_source_dijkstra" else actual
            for source in sources:
                assert paths[source][0] is source
    assert len(calls) == (2 if uses_native else 0)


@pytest.mark.parametrize("name", _MULTISOURCE_NAMES)
@pytest.mark.parametrize("graph_class", ["Graph", "DiGraph"])
@pytest.mark.parametrize("provider", ["private-rows", "assigned-edges", "attribute-factory"])
def test_multisource_compound_sources_keep_assigned_graph_protocols(
    monkeypatch, name, graph_class, provider
):
    nodes = [(index, "node") for index in range(3)]
    graphs = []
    for library in (fnx, nx):
        graph = getattr(library, graph_class)()
        graph.add_weighted_edges_from([
            (nodes[0], nodes[1], 1), (nodes[1], nodes[2], 3),
        ])
        if provider == "private-rows":
            rows = {node: {} for node in nodes}
            rows[nodes[0]][nodes[2]] = {"weight": 0.25}
            if graph_class == "Graph":
                rows[nodes[2]][nodes[0]] = rows[nodes[0]][nodes[2]]
            graph._adj = rows
        elif provider == "assigned-edges":
            def edges(*args, **kwargs):
                raise AssertionError("shortest-path search read an assigned edge provider")

            graph.edges = edges
        else:
            class AttributeFactory(dict):
                pass

            graph.edge_attr_dict_factory = AttributeFactory
        graphs.append(graph)

    def prepared_native_graph(*args, **kwargs):
        raise AssertionError("assigned graph protocols reached a native search")

    namespace = fnx.multi_source_dijkstra.__globals__
    monkeypatch.setitem(namespace, "_raw_multi_source_dijkstra", prepared_native_graph)
    monkeypatch.setattr(
        namespace["_fnx"], "multi_source_dijkstra_path_length", prepared_native_graph
    )
    actual = getattr(fnx, name)(graphs[0], [nodes[0]])
    expected = getattr(nx, name)(graphs[1], [nodes[0]], backend="networkx")
    assert _ordered_weighted_value(actual) == _ordered_weighted_value(expected)


@pytest.mark.parametrize("name", _MULTISOURCE_NAMES)
@pytest.mark.parametrize("kind", [
    "tuple", "frozenset", "nested", "tuple-subclass", "frozenset-subclass",
])
@pytest.mark.parametrize("route", ["networkx-input", "backend"])
def test_multisource_compound_source_protocols_precede_conversion(name, kind, route):
    def run(reference):
        graph = nx.DiGraph()
        events = []
        armed = False

        def wrap(value):
            if kind in ("tuple", "tuple-subclass"):
                return (value,)
            if kind in ("frozenset", "frozenset-subclass"):
                return frozenset((value,))
            return (frozenset((value,)), ("cell",))

        source, middle, target = map(wrap, ("s", "a", "t"))
        graph.add_weighted_edges_from([
            (source, middle, 1), (middle, target, 9), (source, target, 8),
        ])

        def observe(operation):
            if armed:
                events.append(operation)
                graph[middle][target]["weight"] = 1

        class LabelMeta(type):
            def __eq__(cls, other):
                raise AssertionError("a caller's label type was compared")

            def __hash__(cls):
                raise AssertionError("a caller's label type was hashed")

        class ScalarLabel(str, metaclass=LabelMeta):
            def __hash__(self):
                observe("hash")
                return str.__hash__(self)

            def __eq__(self, other):
                observe("equal")
                return str.__eq__(self, other)

        class TupleLabel(tuple):
            def __hash__(self):
                observe("hash")
                return tuple.__hash__(self)

            def __iter__(self):
                raise AssertionError("a caller's node label was iterated")

        class FrozenLabel(frozenset):
            def __hash__(self):
                observe("hash")
                return frozenset.__hash__(self)

            def __iter__(self):
                raise AssertionError("a caller's node label was iterated")

            def __repr__(self):
                return "FrozenLabel(source)"

        if kind == "tuple-subclass":
            supplied = TupleLabel(source)
        elif kind == "frozenset-subclass":
            supplied = FrozenLabel(source)
        else:
            supplied = wrap(ScalarLabel("s"))
        armed = True
        actual = (
            getattr(fnx, name)(graph, [supplied])
            if not reference and route == "networkx-input" else
            getattr(nx, name)(
                graph, [supplied],
                backend="networkx" if reference else "franken_networkx",
            )
        )
        if name == "multi_source_dijkstra_path":
            assert actual[target][0] is supplied
            assert len(actual[target]) == 3
        else:
            distances = actual[0] if name == "multi_source_dijkstra" else actual
            assert distances[target] == 2
        return repr(actual), events

    assert run(False) == run(True)


@pytest.mark.parametrize("name", _WEIGHTED_ROUTE_NAMES)
@pytest.mark.parametrize("weight", [None, "", 0])
@pytest.mark.parametrize("prewarmed", [False, True])
def test_weighted_query_backend_family_preserves_literal_weight_selectors(
    name, weight, prewarmed
):
    graph = nx.DiGraph()
    graph.add_edges_from([
        ("s", "a", {weight: 2}), ("a", "t", {weight: 3}),
        ("s", "t", {weight: 9}),
    ])
    args = (["s"],) if name in _MULTISOURCE_NAMES else ("s",)
    if name == "bidirectional_dijkstra":
        args = ("s", "t")
    expected = getattr(nx, name)(graph, *args, weight=weight, backend="networkx")
    if prewarmed:
        _prewarm_weighted_backend(graph)
    result = getattr(nx, name)(graph, *args, weight=weight, backend="franken_networkx")
    assert _ordered_weighted_value(result) == _ordered_weighted_value(expected)


@pytest.mark.parametrize("name,args,options", [
    ("multi_source_dijkstra", ([],), {}),
    ("multi_source_dijkstra", (["missing"],), {}),
    ("multi_source_dijkstra", (["s"],), {"target": "isolated"}),
    ("multi_source_dijkstra_path", ([],), {}),
    ("multi_source_dijkstra_path", (["missing"],), {}),
    ("multi_source_dijkstra_path_length", ([],), {}),
    ("multi_source_dijkstra_path_length", (["missing"],), {}),
    ("dijkstra_predecessor_and_distance", ("missing",), {}),
    ("bidirectional_dijkstra", ("missing", "t"), {}),
    ("bidirectional_dijkstra", ("s", "missing"), {}),
    ("bidirectional_dijkstra", ("s", "isolated"), {}),
])
@pytest.mark.parametrize("prewarmed", [False, True])
def test_weighted_query_backend_family_preserves_public_errors(
    name, args, options, prewarmed
):
    graph = _weighted_route_graph(nx, "DiGraph")
    expected = _weighted_outcome(
        lambda: getattr(nx, name)(graph, *args, backend="networkx", **options)
    )
    assert expected[0] == "raise"
    if prewarmed:
        _prewarm_weighted_backend(graph)
    assert _weighted_outcome(
        lambda: getattr(nx, name)(graph, *args, backend="franken_networkx", **options)
    ) == expected


def _reciprocal_weight_graph(graph_class):
    graph = getattr(nx, graph_class)()
    graph.add_nodes_from(["s", "a", "t", "isolated"])
    graph.add_weighted_edges_from([
        ("s", "a", 2), ("s", "t", 4), ("t", "a", 3),
    ])
    if graph.is_multigraph():
        graph.add_edge("s", "a", key="parallel", weight=9)
    return graph


@pytest.mark.parametrize("graph_class", _GRAPH_CLASSES)
@pytest.mark.parametrize("name", ["shortest_path", "shortest_path_length"])
@pytest.mark.parametrize("mutation", ["weight", "missing-edge"])
@pytest.mark.parametrize("route", ["direct", "backend", "warm-backend"])
def test_weighted_target_queries_preserve_separate_reciprocal_rows(
    graph_class, name, mutation, route
):
    graph = _reciprocal_weight_graph(graph_class)
    if route == "warm-backend":
        nx.shortest_path_length(
            graph, "s", "a", weight="weight", backend="franken_networkx"
        )
        assert graph.__networkx_cache__["backends"]["franken_networkx"]

    # NetworkX searches the supplied rows. A native conversion would repair
    # these independent dictionaries, reintroducing a cost-2 reverse edge.
    rows = graph._pred if graph.is_directed() else graph._adj
    if mutation == "missing-edge":
        del rows["a"]["s"]
    else:
        rows["a"]["s"] = (
            {0: {"weight": 20}, "parallel": {"weight": 25}}
            if graph.is_multigraph() else {"weight": 20}
        )
    options = {"target": "a", "weight": "weight"}
    expected = getattr(nx, name)(graph, backend="networkx", **options)
    assert expected["s"] == (["s", "t", "a"] if name == "shortest_path" else 7)
    for _ in range(2):
        actual = (
            getattr(fnx, name)(graph, **options)
            if route == "direct" else
            getattr(nx, name)(graph, backend="franken_networkx", **options)
        )
        assert _ordered_weighted_value(actual) == _ordered_weighted_value(expected)


@pytest.mark.parametrize("graph_class", ["Graph", "MultiGraph"])
@pytest.mark.parametrize("name", [
    "single_source_dijkstra", "single_source_dijkstra_path_length",
    "multi_source_dijkstra", "multi_source_dijkstra_path_length",
    "dijkstra_predecessor_and_distance",
])
@pytest.mark.parametrize("route", ["direct", "backend", "warm-backend"])
def test_weighted_source_queries_preserve_separate_reciprocal_rows(
    graph_class, name, route
):
    graph = _reciprocal_weight_graph(graph_class)
    if route == "warm-backend":
        nx.dijkstra_path_length(graph, "s", "a", backend="franken_networkx")
        assert graph.__networkx_cache__["backends"]["franken_networkx"]
    graph._adj["a"]["s"] = (
        {0: {"weight": 20}} if graph.is_multigraph() else {"weight": 20}
    )
    source = ["a"] if name.startswith("multi_source") else "a"
    expected = getattr(nx, name)(graph, source, backend="networkx")
    actual = (
        getattr(fnx, name)(graph, source)
        if route == "direct" else
        getattr(nx, name)(graph, source, backend="franken_networkx")
    )
    assert _ordered_weighted_value(actual) == _ordered_weighted_value(expected)


@pytest.mark.parametrize("graph_class", _GRAPH_CLASSES)
@pytest.mark.parametrize("mutation", ["missing-isolate", "extra-source"])
@pytest.mark.parametrize("route", ["direct", "backend", "warm-backend"])
def test_weighted_queries_preserve_private_node_coverage(graph_class, mutation, route):
    graph = _reciprocal_weight_graph(graph_class)
    if route == "warm-backend":
        nx.dijkstra_path_length(graph, "s", "a", backend="franken_networkx")
        assert graph.__networkx_cache__["backends"]["franken_networkx"]
    if mutation == "missing-isolate":
        # The missing row is outside the reached component; copying every
        # node before searching would raise an unrelated KeyError.
        del graph._adj["isolated"]
        source = "s"
    else:
        graph._adj["ghost"] = {}
        graph._adj["t"]["ghost"] = (
            {0: {"weight": 1}} if graph.is_multigraph() else {"weight": 1}
        )
        # Conversion would add this endpoint to _node and make an invalid
        # source pass membership validation.
        source = "ghost"
    expected = _weighted_outcome(
        lambda: nx.single_source_dijkstra(graph, source, backend="networkx")
    )
    if mutation == "missing-isolate":
        assert expected[0] == "return"
    else:
        assert expected[:2] == ("raise", "NodeNotFound")
    actual = _weighted_outcome(
        lambda: fnx.single_source_dijkstra(graph, source)
        if route == "direct" else
        nx.single_source_dijkstra(graph, source, backend="franken_networkx")
    )
    assert actual == expected


@pytest.mark.parametrize("graph_class", _GRAPH_CLASSES)
def test_consistent_weighted_rows_retain_native_search(monkeypatch, graph_class):
    graph = _reciprocal_weight_graph(graph_class)
    expected = nx.multi_source_dijkstra(graph, ["s"], backend="networkx")
    namespace = fnx.multi_source_dijkstra.__globals__

    def left_native(*args, **kwargs):
        raise AssertionError("consistent NetworkX storage left its native route")

    monkeypatch.setitem(namespace, "_multi_source_dijkstra_inproc", left_native)
    monkeypatch.setitem(namespace, "_dijkstra_multisource_inproc", left_native)
    assert namespace["_weighted_query_uses_live_python_rows"](graph, "weight") is False
    assert _ordered_weighted_value(fnx.multi_source_dijkstra(graph, ["s"])) == (
        _ordered_weighted_value(expected)
    )


@pytest.mark.parametrize("graph_class", _GRAPH_CLASSES)
def test_reciprocal_row_admission_never_compares_attribute_values(graph_class):
    class Uncomparable:
        def __eq__(self, other):
            raise AssertionError("weighted route compared an unrelated attribute")

    graph = _reciprocal_weight_graph(graph_class)
    left = graph._adj["s"]["a"]
    if graph.is_multigraph():
        left = left[0]
    left["payload"] = Uncomparable()
    gate = fnx._weighted_query_uses_live_python_rows
    assert gate(graph, "weight") is False
    rows = graph._pred if graph.is_directed() else graph._adj
    rows["a"]["s"] = (
        {0: {"weight": 2, "payload": Uncomparable()}}
        if graph.is_multigraph() else {"weight": 2, "payload": Uncomparable()}
    )
    assert gate(graph, "weight") is True
