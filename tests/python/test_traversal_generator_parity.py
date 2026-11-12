"""Parity for traversal/path/clique iterator return types.

Bead br-r37-c1-682kr. Eight functions returned ``list`` or
``list_iterator`` (eager Rust materialisation or eager Python list-build)
while nx returns true generators (lazy):

- all_simple_paths, shortest_simple_paths
- enumerate_all_cliques, find_cliques, find_cliques_recursive
- bfs_edges, dfs_edges
- lexicographical_topological_sort

Drop-in code doing ``isinstance(result, types.GeneratorType)`` failed;
short-circuit patterns like ``next(all_simple_paths(huge_graph, ...))``
materialise the entire result on fnx vs. one path on nx — could be
unbounded.

Fix converts each function to a generator (``yield``/``yield from``),
matching nx's lazy evaluation contract.
"""

from __future__ import annotations

import types

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


# ---------------------------------------------------------------------------
# Each entry: function name, factory taking the library that builds the call.
# ---------------------------------------------------------------------------
PROBES = [
    ("all_simple_paths",
     lambda lib: lib.all_simple_paths(lib.path_graph(5), 0, 4)),
    ("shortest_simple_paths",
     lambda lib: lib.shortest_simple_paths(lib.path_graph(5), 0, 4)),
    ("enumerate_all_cliques",
     lambda lib: lib.enumerate_all_cliques(lib.complete_graph(3))),
    ("find_cliques",
     lambda lib: lib.find_cliques(lib.complete_graph(3))),
    ("find_cliques_recursive",
     lambda lib: lib.find_cliques_recursive(lib.complete_graph(3))),
    ("bfs_edges",
     lambda lib: lib.bfs_edges(lib.path_graph(5), 0)),
    ("dfs_edges",
     lambda lib: lib.dfs_edges(lib.path_graph(5), 0)),
    ("lexicographical_topological_sort",
     lambda lib: lib.lexicographical_topological_sort(
         lib.DiGraph([(0, 1), (1, 2)]))),
]


@needs_nx
@pytest.mark.parametrize(
    "name,factory", PROBES,
    ids=[entry[0] for entry in PROBES],
)
def test_returns_generator_like_networkx(name, factory):
    f_result = factory(fnx)
    assert isinstance(f_result, types.GeneratorType), (
        f"fnx.{name} returned {type(f_result).__name__}, expected generator"
    )


@needs_nx
@pytest.mark.parametrize(
    "name,factory", PROBES,
    ids=[entry[0] for entry in PROBES],
)
def test_values_match_networkx(name, factory):
    f_result = list(factory(fnx))
    n_result = list(factory(nx))
    # Some return iterators of lists/tuples in different orders. Compare
    # multiset.
    f_canon = sorted([tuple(p) if isinstance(p, list) else p for p in f_result])
    n_canon = sorted([tuple(p) if isinstance(p, list) else p for p in n_result])
    assert f_canon == n_canon, (
        f"{name}: fnx={f_canon[:3]}... nx={n_canon[:3]}..."
    )


@needs_nx
def test_all_simple_paths_lazy_short_circuit():
    """next() on the generator returns one path immediately."""
    G = fnx.complete_graph(6)
    paths = fnx.all_simple_paths(G, 0, 5)
    first = next(paths)
    assert isinstance(first, list)
    assert first[0] == 0 and first[-1] == 5


@needs_nx
def test_dfs_edges_error_raised_on_iteration_not_call():
    """nx raises NetworkXError when the generator is iterated, not when
    called — fnx now matches this lazy behaviour."""
    G = fnx.path_graph(3)
    # The call should not raise; iteration should.
    gen = fnx.dfs_edges(G, source=99)
    assert isinstance(gen, types.GeneratorType)
    with pytest.raises(fnx.NetworkXError):
        next(gen)


@needs_nx
def test_bfs_edges_error_raised_on_iteration_not_call():
    G = fnx.path_graph(3)
    gen = fnx.bfs_edges(G, source=99)
    assert isinstance(gen, types.GeneratorType)
    with pytest.raises(fnx.NetworkXError):
        next(gen)


@needs_nx
def test_all_simple_paths_source_equals_target_yields_single():
    """When source==target, a single [source] path should yield."""
    G = fnx.path_graph(5)
    paths = fnx.all_simple_paths(G, 2, 2)
    assert isinstance(paths, types.GeneratorType)
    result = list(paths)
    assert result == [[2]]


@needs_nx
def test_find_cliques_with_explicit_nodes_yields_lazily():
    """find_cliques with non-None nodes also yields rather than returning
    a list."""
    G = fnx.complete_graph(5)
    gen = fnx.find_cliques(G, nodes=[0, 1])
    assert isinstance(gen, types.GeneratorType)
    cliques = list(gen)
    assert len(cliques) >= 1


@needs_nx
def test_lexicographical_topological_sort_yields_lazily():
    G = fnx.DiGraph()
    G.add_edges_from([(0, 1), (1, 2), (2, 3)])
    gen = fnx.lexicographical_topological_sort(G)
    assert isinstance(gen, types.GeneratorType)
    first = next(gen)
    assert first == 0


@needs_nx
def test_shortest_simple_paths_yields_lazily():
    G = fnx.complete_graph(5)
    gen = fnx.shortest_simple_paths(G, 0, 4)
    assert isinstance(gen, types.GeneratorType)
    first_path = next(gen)
    assert first_path[0] == 0 and first_path[-1] == 4


def _live_traversal_graph(lib, graph_name, kind):
    graph_lib = nx if kind == "networkx" else lib
    root = getattr(graph_lib, graph_name)()
    root.add_nodes_from(range(5))
    root.add_edges_from([(0, 1), (1, 2)])
    graph = root.subgraph(range(5)) if kind == "subgraph" else root
    return root, graph


@pytest.mark.parametrize("graph_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("kind", ["native", "networkx", "subgraph"])
@pytest.mark.parametrize(
    "name",
    ["bfs_edges", "dfs_edges", "dfs_preorder_nodes", "dfs_postorder_nodes",
     "bfs_predecessors", "bfs_successors", "bfs_layers"],
)
def test_traversals_observe_graph_edits_before_first_iteration(graph_name, kind, name):
    results = []
    for lib in (fnx, nx):
        root, graph = _live_traversal_graph(lib, graph_name, kind)
        traversal = getattr(lib, name)(graph, 0)
        root.add_edge(2, 3)
        results.append(list(traversal))
    assert results[0] == results[1]


@pytest.mark.parametrize("graph_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("kind", ["native", "networkx", "subgraph"])
@pytest.mark.parametrize(
    "name",
    ["bfs_edges", "dfs_edges", "bfs_predecessors", "bfs_successors",
     "dfs_preorder_nodes", "dfs_postorder_nodes", "dfs_labeled_edges",
     "bfs_tree", "dfs_tree", "dfs_predecessors", "dfs_successors"],
)
def test_neighbor_sort_callbacks_walk_the_callers_live_graph(graph_name, kind, name):
    results = []
    for lib in (fnx, nx):
        root, graph = _live_traversal_graph(lib, graph_name, kind)
        calls = []

        def sort_neighbors(neighbors):
            row = list(neighbors)
            if not calls:
                root.add_edge(2, 3)
            calls.append(row)
            return row

        traversal = getattr(lib, name)(graph, 0, sort_neighbors=sort_neighbors)
        if name.endswith("tree"):
            result = (list(traversal), list(traversal.edges()))
        elif isinstance(traversal, dict):
            result = list(traversal.items())
        else:
            result = list(traversal)
        results.append((result, calls))
    assert results[0] == results[1]


@pytest.mark.parametrize("graph_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("kind", ["native", "networkx", "subgraph"])
def test_bfs_layers_expands_each_frontier_only_after_it_is_yielded(graph_name, kind):
    results = []
    for lib in (fnx, nx):
        root, graph = _live_traversal_graph(lib, graph_name, kind)
        layers = lib.bfs_layers(graph, 0)
        first = next(layers)
        root.add_edge(0, 3)
        second = next(layers)
        root.add_edge(3, 4)
        results.append([first, second, *layers])
    assert results[0] == results[1] == [[0], [1, 3], [2, 4]]


@pytest.mark.parametrize("graph_name", ["Graph", "DiGraph"])
def test_bfs_layers_yields_the_mutable_frontier_it_will_expand(graph_name):
    results = []
    for lib in (fnx, nx):
        graph = getattr(lib, graph_name)([(0, 1), (1, 2), (3, 4)])
        layers = lib.bfs_layers(graph, [0])
        frontier = next(layers)
        frontier.append(3)
        results.append([frontier, *layers])
    assert results[0] == results[1]


def _traversal_steps(lib, graph, name, source):
    steps = []
    try:
        traversal = getattr(lib, name)(graph, source)
    except Exception as exc:
        return [("call", type(exc), exc.args)]
    steps.append(("call", "ok"))
    try:
        for value in traversal:
            steps.append(("yield", value))
    except Exception as exc:
        steps.append(("iterate", type(exc), exc.args))
    return steps


@pytest.mark.parametrize("name", ["bfs_edges", "dfs_edges", "dfs_preorder_nodes", "dfs_postorder_nodes"])
@pytest.mark.parametrize("source", [99, [], {}, {1, 2}], ids=["missing", "list", "dict", "set"])
@pytest.mark.parametrize("graph_name", ["Graph", "DiGraph"])
def test_traversal_errors_preserve_lazy_timing_and_partial_results(name, source, graph_name):
    graphs = [getattr(lib, graph_name)([(0, 1)]) for lib in (fnx, nx)]
    assert _traversal_steps(fnx, graphs[0], name, source) == _traversal_steps(
        nx, graphs[1], name, source
    )


@pytest.mark.parametrize("name", ["edge_bfs", "edge_dfs"])
@pytest.mark.parametrize("graph_name", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("kind", ["native", "networkx", "subgraph", "reverse"])
@pytest.mark.parametrize("orientation", ["reverse", "ignore"])
def test_edge_traversal_orientations_accept_live_public_predecessors(
    name, graph_name, kind, orientation
):
    results = []
    for lib in (fnx, nx):
        root, graph = _live_traversal_graph(lib, graph_name, kind)
        root.add_edges_from([(2, 0), (3, 2), (3, 3)])
        if graph.is_multigraph():
            root.add_edge(0, 1, key="parallel")
        if kind == "reverse":
            graph = root.reverse(copy=False)
        traversal = getattr(lib, name)(graph, 2, orientation=orientation)
        root.add_edge(4, 3)
        results.append(list(traversal))
    assert results[0] == results[1]


@pytest.mark.parametrize("name", ["bfs_edges", "dfs_edges", "dfs_preorder_nodes", "dfs_postorder_nodes"])
def test_native_traversal_generators_accept_send_and_preserve_thrown_exceptions(name):
    results = []
    for lib in (fnx, nx):
        graph = lib.path_graph(6)
        traversal = getattr(lib, name)(graph, 0)
        values = [next(traversal), traversal.send("ignored by traversal")]
        error = nx.NodeNotFound("caller-owned exception")
        with pytest.raises(nx.NodeNotFound) as caught:
            traversal.throw(error)
        assert caught.value is error
        results.append(values)
    assert results[0] == results[1]


@pytest.mark.parametrize("name", ["bfs_edges", "dfs_edges", "dfs_preorder_nodes", "dfs_postorder_nodes"])
@pytest.mark.parametrize("depth", [0, -1, 0.5, 1.5, float("nan"), float("inf"), 1 << 100])
def test_traversal_depth_values_match_without_lossy_native_coercion(name, depth):
    graphs = [lib.Graph([(0, 1), (0, 2), (1, 3), (3, 4), (2, 5)]) for lib in (fnx, nx)]
    assert list(getattr(fnx, name)(graphs[0], 0, depth_limit=depth)) == list(
        getattr(nx, name)(graphs[1], 0, depth_limit=depth)
    )


def test_bfs_layers_does_not_read_adjacency_before_the_first_frontier():
    for lib in (fnx, nx):
        reads = []

        class ObservedGraph(lib.Graph):
            def __getitem__(self, node):
                reads.append(node)
                return super().__getitem__(node)

        graph = ObservedGraph([(0, 1), (1, 2)])
        layers = lib.bfs_layers(graph, 0)
        assert reads == []
        assert next(layers) == [0]
        assert reads == []
        assert next(layers) == [1]
        assert reads == [0]
        layers.close()
