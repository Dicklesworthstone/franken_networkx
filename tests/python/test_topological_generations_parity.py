"""Post-w7nn3 delegation re-audit find: topological_generations
lexicographically sorted each generation (string order put "10" before
"2") instead of nx's node-iteration order (gen 0) / zero-reach order
(later gens), and displayed members as node-map objects instead of the
zeroing parent's succ-row object (discovery-object class).
"""

import random

import networkx as nx
import pytest

import franken_networkx as fnx


def _rr(gens):
    return [[repr(n) for n in gen] for gen in gens]


def test_no_lexicographic_string_sort():
    gn, gf = nx.DiGraph(), fnx.DiGraph()
    for g in (gn, gf):
        for i in range(14):
            g.add_edge("root", i)
    assert _rr(fnx.topological_generations(gf)) == _rr(nx.topological_generations(gn))


def test_zero_reach_order_within_generation():
    gn, gf = nx.DiGraph(), fnx.DiGraph()
    for g in (gn, gf):
        for e in [(0, 2), (1, 2), (0, 1), (2, 4), (2, 3), (3, 5), (4, 5), (0, 5)]:
            g.add_edge(*e)
    assert _rr(fnx.topological_generations(gf)) == _rr(nx.topological_generations(gn))


def test_multigraph_parallel_edge_decrement():
    gn, gf = nx.MultiDiGraph(), fnx.MultiDiGraph()
    for g in (gn, gf):
        g.add_edge(0, 1)
        g.add_edge(0, 1)
        g.add_edge(1, 2)
        g.add_edge(0, 2)
    assert _rr(fnx.topological_generations(gf)) == _rr(nx.topological_generations(gn))


def test_mixed_key_zeroing_parent_row_objects():
    gn, gf = nx.DiGraph(), fnx.DiGraph()
    for g in (gn, gf):
        g.add_node(28)
        g.add_edge(7, 28.0)
        g.add_edge(28.0, 5)
    assert _rr(fnx.topological_generations(gf)) == _rr(nx.topological_generations(gn))


def test_random_dag_corpus():
    rnd = random.Random(31)
    for trial in range(20):
        n = rnd.randrange(4, 16)
        gn, gf = nx.DiGraph(), fnx.DiGraph()
        for g in (gn, gf):
            g.add_nodes_from(range(n))
        for _ in range(rnd.randrange(3, 30)):
            u, v = rnd.randrange(n), rnd.randrange(n)
            if u < v:
                gn.add_edge(u, v)
                gf.add_edge(u, v)
        assert _rr(fnx.topological_generations(gf)) == _rr(
            nx.topological_generations(gn)
        ), trial


def test_cycle_raises_unfeasible():
    gf = fnx.DiGraph([(1, 2), (2, 1)])
    with pytest.raises(fnx.NetworkXUnfeasible):
        list(fnx.topological_generations(gf))


# nro4w.11: networkx processes each generation (each node, for the
# lexicographical sort) on the LIVE graph just before yielding it. A caller that
# mutates the graph mid-iteration gets RuntimeError or NetworkXUnfeasible at
# exactly the point networkx notices, and a cyclic graph yields its acyclic
# prefix before NetworkXUnfeasible.

import inspect

SORTS = ("topological_generations", "topological_sort", "lexicographical_topological_sort")


def _drive(mod, fn, graph, mutations):
    """Iterate ``fn(graph)``, applying ``mutations[i]`` after the i-th yield."""
    out = []
    try:
        for i, item in enumerate(getattr(mod, fn)(graph)):
            out.append([repr(n) for n in item] if isinstance(item, list) else repr(item))
            for mutate in mutations.get(i, ()):
                mutate(graph)
        return out, None, None
    except Exception as err:  # the exception is part of the contract under test
        return out, type(err).__name__, str(err)


def _pair(cls, edges, nodes=()):
    gn, gf = getattr(nx, cls)(), getattr(fnx, cls)()
    for g in (gn, gf):
        g.add_nodes_from(nodes)
        g.add_edges_from(edges)
    return gn, gf


@pytest.mark.parametrize("fn", ["topological_sort", "lexicographical_topological_sort"])
@pytest.mark.parametrize(
    "mutate, expected",
    [
        # networkx's test_dag.py::test_topological_sort6, after the first yield.
        (lambda G, x: G.add_edge(5 - x, 5), ([1, 2, 3], "RuntimeError")),
        (lambda G, x: G.remove_node(4), ([1, 2, 3], "NetworkXUnfeasible")),
        (lambda G, x: G.remove_node(2), ([1], "RuntimeError")),
    ],
)
def test_networkx_mutation_scenarios(fn, mutate, expected):
    G = fnx.DiGraph([(1, 2), (2, 3), (3, 4)])
    seen = []
    with pytest.raises(Exception) as info:
        for x in getattr(fnx, fn)(G):
            seen.append(x)
            if len(seen) == 1:
                mutate(G, x)
    assert (seen, type(info.value).__name__) == expected


@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("fn", SORTS)
def test_cyclic_graph_yields_the_acyclic_prefix_first(cls, fn):
    gn, gf = _pair(cls, [(0, 1), (1, 2), (2, 1), (0, 3), (3, 4), (5, 5)], nodes=[6])
    expected = _drive(nx, fn, gn, {})
    assert expected[1] == "NetworkXUnfeasible" and expected[0]
    assert _drive(fnx, fn, gf, {}) == expected


@pytest.mark.parametrize("fn", SORTS)
def test_the_sorts_are_generator_functions(fn):
    assert inspect.isgeneratorfunction(getattr(fnx, fn)) == inspect.isgeneratorfunction(
        getattr(nx, fn)
    )


class _SubDiGraph(fnx.DiGraph):
    pass


def _random_mutation(rnd, multigraph):
    kind = rnd.choice(
        ["edge", "edge", "new_child", "new_parent", "remove_node", "remove_edge",
         "add_node", "edges", "clear_edges"] + (["parallel", "parallel"] if multigraph else [])
    )
    a, b = rnd.randrange(12), rnd.randrange(12)

    def mutate(G):
        nodes = list(G)
        if kind in ("edge", "parallel") and nodes:
            u, v = nodes[a % len(nodes)], nodes[b % len(nodes)]
            G.add_edge(u, v)
        elif kind == "new_child" and nodes:
            G.add_edge(nodes[a % len(nodes)], 100 + b)
        elif kind == "new_parent" and nodes:
            G.add_edge(100 + b, nodes[a % len(nodes)])
        elif kind == "remove_node" and nodes:
            G.remove_node(nodes[a % len(nodes)])
        elif kind == "remove_edge":
            edges = list(G.edges())
            if edges:
                G.remove_edge(*edges[a % len(edges)])
        elif kind == "add_node":
            G.add_node(200 + a)
        elif kind == "edges" and nodes:
            G.add_edges_from([(nodes[a % len(nodes)], nodes[(a + b) % len(nodes)]), (nodes[b % len(nodes)], 300)])
        elif kind == "clear_edges":
            G.clear_edges()

    return mutate


@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
def test_random_mutation_during_iteration_matches_networkx(cls):
    rnd = random.Random(20260924)
    multigraph = cls == "MultiDiGraph"
    for trial in range(300):
        n = rnd.randrange(1, 10)
        edges = []
        for _ in range(rnd.randrange(0, 18)):
            u, v = rnd.randrange(n), rnd.randrange(n)
            if u < v or rnd.random() < 0.08:  # mostly acyclic, sometimes not
                edges.append((u, v))
        schedule = {}
        for _ in range(rnd.randrange(0, 3)):
            schedule.setdefault(rnd.randrange(0, n + 1), []).append(_random_mutation(rnd, multigraph))
        for fn in SORTS:
            gn, gf = _pair(cls, edges, nodes=range(n))
            expected = _drive(nx, fn, gn, schedule)
            assert _drive(fnx, fn, gf, schedule) == expected, (trial, fn, edges, expected)
            if cls == "DiGraph":
                sub = _SubDiGraph()
                sub.add_nodes_from(range(n))
                sub.add_edges_from(edges)
                assert _drive(fnx, fn, sub, schedule) == expected, ("subclass", trial, fn)
                nx_input = nx.DiGraph()
                nx_input.add_nodes_from(range(n))
                nx_input.add_edges_from(edges)
                assert _drive(fnx, fn, nx_input, schedule) == expected, ("nx input", trial, fn)


@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("fn", ["topological_generations", "topological_sort"])
@pytest.mark.parametrize("assign_before_start", [False, True])
def test_assigned_rows_remain_live_between_topological_yields(cls, fn, assign_before_start):
    def run(module):
        graph = getattr(module, cls)([(0, 1), (1, 2), (2, 3)])
        logical = getattr(nx, cls)([(0, 1), (1, 2), (2, 3)])

        def assign():
            graph._node = logical._node
            graph._succ = logical._succ
            graph._pred = logical._pred

        if assign_before_start:
            assign()

        def mutate(_graph):
            if not assign_before_start:
                assign()
            # This does not advance the original native graph's revision.
            # The held traversal must still notice the new, uncounted child.
            logical.add_edge(1, 9)

        return _drive(module, fn, graph, {0: [mutate]})

    expected = run(nx)
    assert expected[1] == "RuntimeError"
    assert run(fnx) == expected


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("algorithm", ["topological_generations", "topological_sort"])
@pytest.mark.parametrize("warm_degree", [False, True])
def test_topological_public_readers_run_in_reference_order(
    graph_type, algorithm, warm_degree
):
    def run(module):
        graph = getattr(module, graph_type)([(0, 1), (1, 2)])
        if warm_degree:
            _ = graph.in_degree
        events = []

        def directed():
            events.append("directed")
            return True

        def multigraph():
            events.append("multigraph")
            return graph_type == "MultiDiGraph"

        def in_degree():
            events.append("in_degree")
            return iter([(0, 0), (1, 1), (2, 1)])

        def neighbors(node):
            events.append(("neighbors", node))
            return iter({0: [1], 1: [2], 2: []}[node])

        graph.is_directed = directed
        graph.is_multigraph = multigraph
        graph.in_degree = in_degree
        graph.neighbors = neighbors
        iterator = getattr(module, algorithm)(graph)
        assert events == []
        return list(iterator), events

    expected = run(nx)
    assert expected[1][:4] == ["directed", "multigraph", "in_degree", "in_degree"]
    assert run(fnx) == expected


@pytest.mark.parametrize("algorithm", ["topological_generations", "topological_sort"])
def test_multigraph_kind_is_captured_before_degree_providers(algorithm):
    def run(module):
        graph = module.MultiDiGraph([(0, 1), (0, 1), (1, 2)])

        def in_degree():
            graph.is_multigraph = lambda: False
            return iter([(0, 0), (1, 2), (2, 1)])

        graph.in_degree = in_degree
        return _drive(module, algorithm, graph, {})

    expected = run(nx)
    assert expected[1] is None
    assert run(fnx) == expected


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("algorithm", ["topological_generations", "topological_sort"])
@pytest.mark.parametrize("scope", ["instance", "class"])
@pytest.mark.parametrize("before_start", [False, True])
def test_topological_neighbor_replacements_stay_live(
    monkeypatch, graph_type, algorithm, scope, before_start
):
    def run(module):
        graph_class = getattr(module, graph_type)
        graph = graph_class([(0, 1), (1, 2), (1, 3), (2, 4), (3, 4)])
        original = graph_class.neighbors
        events = []

        def neighbors(self, node):
            events.append(node)
            return iter(reversed(list(original(self, node))))

        with monkeypatch.context() as patcher:
            def install(_graph):
                if scope == "class":
                    patcher.setattr(graph_class, "neighbors", neighbors)
                else:
                    graph.neighbors = lambda node: neighbors(graph, node)

            if before_start:
                install(graph)
            schedule = {} if before_start else {0: [install]}
            return _drive(module, algorithm, graph, schedule), events

    expected = run(nx)
    assert expected[0][1] is None and expected[1]
    assert run(fnx) == expected


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("algorithm", ["topological_generations", "topological_sort"])
def test_suspended_topology_keeps_original_multigraph_flag(graph_type, algorithm):
    def run(module):
        graph = getattr(module, graph_type)([(0, 1), (1, 2)])

        def mutate(graph):
            graph.add_node("later")

            def multigraph():
                raise AssertionError("multigraph kind was read after traversal started")

            graph.is_multigraph = multigraph

        return _drive(module, algorithm, graph, {0: [mutate]})

    expected = run(nx)
    assert expected[1] is None
    assert run(fnx) == expected


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("algorithm", ["topological_generations", "topological_sort"])
@pytest.mark.parametrize("label_kind", ["node", "row_alias"])
def test_topology_does_not_skip_node_hash_exceptions(graph_type, algorithm, label_kind):
    def run(module):
        armed = False

        class Label(int):
            def __hash__(self):
                if armed:
                    raise RuntimeError("topological node hash callback")
                return int.__hash__(self)

        graph = getattr(module, graph_type)()
        if label_kind == "node":
            graph.add_edges_from([(Label(0), Label(1)), (Label(1), Label(2))])
        else:
            graph.add_nodes_from(range(3))
            graph.add_edges_from([(0, Label(1)), (1, 2)])
        armed = True
        return _drive(module, algorithm, graph, {})

    expected = run(nx)
    assert expected[1:] == ("RuntimeError", "topological node hash callback")
    assert run(fnx) == expected


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("warm_degree", [False, True])
def test_plain_topological_generations_keep_native_batch(monkeypatch, graph_type, warm_degree):
    edges = [(0, 1), (0, 2), (1, 3), (2, 3)]
    graph = getattr(fnx, graph_type)(edges)
    reference = getattr(nx, graph_type)(edges)
    if warm_degree:
        _ = graph.in_degree
    calls = []
    original = fnx._raw_topological_generations_state

    def capture(graph):
        calls.append(graph)
        return original(graph)

    monkeypatch.setattr(fnx, "_raw_topological_generations_state", capture)
    assert list(fnx.topological_generations(graph)) == list(nx.topological_generations(reference))
    assert len(calls) == 1 and calls[0] is graph


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("input_module", [nx, fnx], ids=["networkx", "franken_networkx"])
def test_dag_predicate_reads_logical_degree_provider(graph_type, input_module):
    graph = getattr(input_module, graph_type)([(0, 1), (1, 2)])
    reference = getattr(nx, graph_type)([(0, 1), (1, 2)])
    for current in (graph, reference):
        current.in_degree = lambda: [(0, 1), (1, 1), (2, 1)]
    expected = nx.is_directed_acyclic_graph(reference)
    assert expected is False
    assert fnx.is_directed_acyclic_graph(graph) is expected


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("warm_cache", [False, True])
def test_backend_dag_predicate_preserves_original_providers(graph_type, warm_cache):
    graph = getattr(nx, graph_type)([(0, 1), (1, 2)])
    reference = getattr(nx, graph_type)([(0, 1), (1, 2)])
    with nx.config(cache_converted_graphs=True):
        if warm_cache:
            assert nx.dijkstra_path_length(graph, 0, 2, backend="franken_networkx") == 2
            assert graph.__networkx_cache__.get("backends", {}).get("franken_networkx")
        for current in (graph, reference):
            current.in_degree = lambda: [(0, 1), (1, 1), (2, 1)]
        assert nx.is_directed_acyclic_graph(reference) is False
        assert nx.is_directed_acyclic_graph(graph, backend="franken_networkx") is False


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
def test_dag_predicate_keeps_falsy_directedness_value(graph_type):
    graph = getattr(fnx, graph_type)([(0, 1)])
    reference = getattr(nx, graph_type)([(0, 1)])
    graph.is_directed = lambda: None
    reference.is_directed = lambda: None
    assert fnx.is_directed_acyclic_graph(graph) is nx.is_directed_acyclic_graph(reference) is None


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
def test_backend_dag_predicate_preserves_provider_exception(graph_type):
    graph = getattr(nx, graph_type)([(0, 1)])

    def in_degree():
        raise nx.NetworkXNotImplemented("custom degree provider")

    graph.in_degree = in_degree
    with pytest.raises(nx.NetworkXNotImplemented, match="custom degree provider"):
        nx.is_directed_acyclic_graph(graph, backend="franken_networkx")


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("kind", ["canonical", "filtered", "nested", "conversion", "subclass", "private"])
@pytest.mark.parametrize("scope", ["instance", "class"])
def test_reverse_dag_predicate_keeps_live_degree_providers(monkeypatch, graph_type, kind, scope):
    def run(module):
        graph = getattr(module, graph_type)([(0, 1), (1, 2), (2, 3)])
        if kind == "filtered":
            view = graph.subgraph([0, 1, 2]).reverse(copy=False)
        elif kind == "nested":
            first = graph.reverse(copy=False)
            view = (
                module._reverse_directed_view_for(first)
                if module is fnx else nx.classes.graphviews.reverse_view(first)
            )
        elif kind == "conversion":
            view = graph.to_undirected(as_view=True).to_directed(as_view=True).reverse(copy=False)
        elif kind == "subclass":
            class CustomGraph(getattr(module, graph_type)):
                pass

            graph = CustomGraph(graph)
            view = graph.reverse(copy=False)
        elif kind == "private":
            graph._succ = {node: {} for node in graph}
            graph._adj = graph._succ
            graph._pred = {node: {} for node in graph}
            view = graph.reverse(copy=False)
        else:
            view = graph.reverse(copy=False)
        nodes = tuple(view)
        calls = []

        def in_degree():
            calls.append("degree")
            return [(node, 1) for node in nodes]

        with monkeypatch.context() as patcher:
            if scope == "instance":
                view.in_degree = in_degree
            else:
                patcher.setattr(type(view), "in_degree", lambda self: in_degree())
            return module.is_directed_acyclic_graph(view), calls

    expected = run(nx)
    assert expected == (False, ["degree", "degree"])
    assert run(fnx) == expected


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("label_kind", ["node", "predecessor_alias"])
def test_reverse_dag_predicate_preserves_node_hash_exceptions(graph_type, label_kind):
    def run(module):
        armed = False

        class Label(int):
            def __hash__(self):
                if armed:
                    raise RuntimeError("reverse DAG node hash callback")
                return int.__hash__(self)

        graph = getattr(module, graph_type)()
        if label_kind == "node":
            graph.add_edges_from([(Label(0), Label(1)), (Label(1), Label(2))])
        else:
            graph.add_nodes_from(range(3))
            graph.add_edges_from([(Label(0), 1), (1, 2)])
        view = graph.reverse(copy=False)
        armed = True
        with pytest.raises(RuntimeError, match="reverse DAG node hash callback"):
            module.is_directed_acyclic_graph(view)

    run(nx)
    run(fnx)
