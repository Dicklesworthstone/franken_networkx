"""Closeness / harmonic centrality identities (centrality <-> distances).

On a connected graph these centralities are defined directly from the shortest-
path distances, so they cross-check all_pairs_shortest_path_length:
  - closeness(v) = (n - 1) / sum_u d(v, u);
  - harmonic(v) = sum_{u != v} 1 / d(v, u);
  - closeness(v) <= 1 (maximised when v is adjacent to every other node).
Oracle-free, independent of networkx.

"On a connected graph" is the interesting part of that sentence: the sweep below
skips 10 of its 40 draws for being disconnected, and disconnectedness is exactly
where these two functions stop agreeing with the simple formulas. Closeness then
uses only the nodes REACHABLE from v, and by default scales by the fraction of
the graph that is reachable (the Wasserman-Faust correction, wf_improved=True) —
a parameter that makes no difference on a connected graph and so was never
exercised. Harmonic needs no correction, since an unreachable node contributes
1/inf = 0. All three are pinned below, still oracle-free.

The source-subset regressions additionally pin NetworkX's exact values, value
types, iteration order, and the native route. No mocks: real fnx and NetworkX.
"""

from __future__ import annotations

import inspect
import random
import sys

import pytest
import franken_networkx as fnx
import networkx as nx


def _connected(seed):
    r = random.Random(seed)
    n = r.randint(5, 10)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.4]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)
    return g, n


@pytest.mark.parametrize("seed", range(40))
def test_closeness_and_harmonic_from_distances(seed):
    g, n = _connected(seed)
    if not fnx.is_connected(g) or g.number_of_edges() == 0:
        pytest.skip("disconnected / empty")
    apsp = dict(fnx.all_pairs_shortest_path_length(g))
    clo = fnx.closeness_centrality(g)
    har = fnx.harmonic_centrality(g)
    for v in g:
        distsum = sum(apsp[v][u] for u in g if u != v)
        assert distsum > 0
        assert abs(clo[v] - (n - 1) / distsum) < 1e-6
        expected_har = sum(1 / apsp[v][u] for u in g if u != v)
        assert abs(har[v] - expected_har) < 1e-6
        assert clo[v] <= 1 + 1e-9


def _disconnected_seeds(limit=200):
    """Seeds whose draw is disconnected, so the sweep below skips nothing.

    Parametrising over range(limit) and skipping would report ~150 skips and
    bury the 47 cases that actually run.
    """
    out = []
    for seed in range(limit):
        g, _ = _connected(seed)
        if g.number_of_edges() and not fnx.is_connected(g):
            out.append(seed)
    return out


DISCONNECTED_SEEDS = _disconnected_seeds()


@pytest.mark.parametrize("seed", DISCONNECTED_SEEDS)
def test_disconnected_uses_only_reachable_nodes(seed):
    """The case the sweep above skips: closeness over the reachable set only.

    closeness(v)     = (R / sum_reachable d) * (R / (n - 1))   [wf_improved=True]
    closeness(v)     =  R / sum_reachable d                    [wf_improved=False]
    harmonic(v)      = sum over REACHABLE of 1 / d             [unreachable -> 0]

    where R is the number of nodes reachable from v, excluding v itself.
    """
    g, n = _connected(seed)
    apsp = dict(fnx.all_pairs_shortest_path_length(g))
    scaled = fnx.closeness_centrality(g)
    unscaled = fnx.closeness_centrality(g, wf_improved=False)
    har = fnx.harmonic_centrality(g)

    for v in g:
        reachable = {u: d for u, d in apsp[v].items() if u != v}
        count = len(reachable)
        if count == 0:                       # isolated node: nothing to be close to
            assert scaled[v] == 0 and unscaled[v] == 0 and har[v] == 0
            continue
        total = sum(reachable.values())
        assert abs(unscaled[v] - count / total) < 1e-9
        assert abs(scaled[v] - (count / total) * (count / (n - 1))) < 1e-9
        assert abs(har[v] - sum(1 / d for d in reachable.values())) < 1e-9
        # The correction only ever shrinks the value, and matches when connected.
        assert scaled[v] <= unscaled[v] + 1e-12


def test_wf_correction_is_the_identity_on_connected_graphs():
    """Guards the parameter's meaning: it is a no-op exactly when R == n-1."""
    g = fnx.path_graph(6)
    assert fnx.is_connected(g)
    scaled = fnx.closeness_centrality(g)
    unscaled = fnx.closeness_centrality(g, wf_improved=False)
    assert all(abs(scaled[v] - unscaled[v]) < 1e-12 for v in g)

    # ...and genuinely differs once the graph splits, so the guard is not vacuous.
    h = fnx.Graph(); h.add_edges_from([(0, 1), (1, 2), (3, 4)])
    assert fnx.closeness_centrality(h) != fnx.closeness_centrality(h, wf_improved=False)


def test_star_center_has_maximal_closeness():
    # In a star, the center is distance 1 from all leaves -> closeness 1;
    # a leaf is distance 1 to center and 2 to other leaves.
    g = fnx.star_graph(5)  # center 0, leaves 1..5
    clo = fnx.closeness_centrality(g)
    assert abs(clo[0] - 1.0) < 1e-9
    assert clo[0] == max(clo.values())
    # Harmonic of the center = number of leaves (all at distance 1).
    har = fnx.harmonic_centrality(g)
    assert abs(har[0] - 5) < 1e-9


def test_complete_graph_all_closeness_one():
    for n in (3, 4, 5):
        clo = fnx.closeness_centrality(fnx.complete_graph(n))
        assert all(abs(c - 1.0) < 1e-9 for c in clo.values())


def _centrality_items_exact(scores):
    return [(node, type(score), score.hex() if isinstance(score, float) else score)
            for node, score in scores.items()]


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("seed", range(6))
@pytest.mark.parametrize("provenance", ["direct", "touched", "copy", "mutated", "view"])
def test_harmonic_source_subset_exact(graph_type, seed, provenance):
    """Replay the real oracle's source set, including aliases and live views."""
    nodes = [1, "root", ("pair", 2), -2, 5, 7, 11, "isolated"]
    fg, ng = getattr(fnx, graph_type)(), getattr(nx, graph_type)()
    rng = random.Random(seed)
    edges = [(u, v) for u in nodes[:-1] for v in nodes[:-1] if rng.random() < 0.25]
    for graph in (fg, ng):
        graph.add_nodes_from(nodes)
        graph.add_edges_from(edges)
        if graph.is_multigraph():
            graph.add_edges_from(edges)
        if provenance == "touched":
            list(graph.edges(data=True))
            list(graph.nodes(data=True))
        elif provenance == "mutated":
            graph.remove_node(-2)
            graph.add_node(-2)
            graph.add_edge(-2, "root")
    if provenance == "copy":
        fg, ng = fg.copy(), ng.copy()
    elif provenance == "view":
        fg, ng = fg.subgraph(nodes), ng.subgraph(nodes)

    for sources in ([], [True, 1.0, ("pair", 2), "missing", 1], nodes[:-1], 1,
                    ("isolated",)):
        expected = nx.harmonic_centrality(ng, sources=sources)
        actual = fnx.harmonic_centrality(fg, sources=sources)
        assert _centrality_items_exact(actual) == _centrality_items_exact(expected)
    expected = nx.harmonic_centrality(ng, sources=(node for node in nodes[::2]))
    actual = fnx.harmonic_centrality(fg, sources=(node for node in nodes[::2]))
    assert _centrality_items_exact(actual) == _centrality_items_exact(expected)


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_harmonic_source_subset_uses_native_kernel(graph_type):
    """Observe real calls, rather than replacing either arm with a mock."""
    fg, ng = getattr(fnx, graph_type)(), getattr(nx, graph_type)()
    for graph in (fg, ng):
        graph.add_edges_from([(0, 1), (1, 2), (2, 3), (0, 3)])
        graph.add_node("isolated")
    expected = nx.harmonic_centrality(ng, sources=[0])
    python_bfs_calls = []
    native_calls = []
    bfs_code = inspect.unwrap(fnx.single_source_shortest_path_length).__code__

    def observe(frame, event, arg):
        if event == "call" and frame.f_code is bfs_code:
            python_bfs_calls.append(frame.f_code.co_name)
        elif event == "c_call" and arg is fnx._raw_harmonic_centrality:
            native_calls.append(arg.__name__)

    previous = sys.getprofile()
    try:
        sys.setprofile(observe)
        actual = fnx.harmonic_centrality(fg, sources=[0])
    finally:
        sys.setprofile(previous)
    assert _centrality_items_exact(actual) == _centrality_items_exact(expected)
    assert not python_bfs_calls, python_bfs_calls
    assert native_calls == ["harmonic_centrality"]
    # An implementation silently dropping the source selection cannot pass.
    assert actual != nx.harmonic_centrality(ng)

    python_bfs_calls.clear()
    native_calls.clear()
    try:
        sys.setprofile(observe)
        empty = fnx.harmonic_centrality(fg, sources=[])
    finally:
        sys.setprofile(previous)
    assert _centrality_items_exact(empty) == _centrality_items_exact(
        nx.harmonic_centrality(ng, sources=[]))
    assert not python_bfs_calls
    assert not native_calls, "empty sources must not project or traverse the graph"


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_harmonic_source_subset_boundaries(graph_type):
    for nodes in ([], ["alone"]):
        fg, ng = getattr(fnx, graph_type)(), getattr(nx, graph_type)()
        fg.add_nodes_from(nodes)
        ng.add_nodes_from(nodes)
        for sources in ([], nodes, ["unknown"]):
            assert _centrality_items_exact(fnx.harmonic_centrality(fg, sources=sources)) == (
                _centrality_items_exact(nx.harmonic_centrality(ng, sources=sources)))
    fg, ng = getattr(fnx, graph_type)(), getattr(nx, graph_type)()
    for graph in (fg, ng):
        graph.add_edges_from([(0, 1, {"distance": 2}), (1, 2, {"distance": 3})])
        graph.add_node("isolated")
    # Weighted and transposed nbunch paths must retain their existing semantics.
    for options in ({"sources": [0], "distance": "distance"},
                    {"sources": [0, 1, 2], "nbunch": [2]},
                    {"sources": [0], "nbunch": [1, 2]}):
        assert _centrality_items_exact(fnx.harmonic_centrality(fg, **options)) == (
            _centrality_items_exact(nx.harmonic_centrality(ng, **options)))

    # Targets are captured before consuming a lazy source iterable. A target
    # removed by that iterable still has its initial integer zero in NetworkX.
    fg, ng = getattr(fnx, graph_type)(), getattr(nx, graph_type)()
    for graph in (fg, ng):
        graph.add_edges_from([(0, 1), (1, 2)])

    def removing_sources(graph):
        graph.remove_node(2)
        yield 0

    assert _centrality_items_exact(fnx.harmonic_centrality(fg, sources=removing_sources(fg))) == (
        _centrality_items_exact(nx.harmonic_centrality(ng, sources=removing_sources(ng))))


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("remove_target", [False, True])
def test_harmonic_source_subset_lazy_growth(graph_type, remove_target):
    """Growing sources can trigger transpose AFTER the targets were captured."""
    fg, ng = getattr(fnx, graph_type)(), getattr(nx, graph_type)()
    for graph in (fg, ng):
        graph.add_edges_from([(2, 1), (1, 0)])

    def growing_sources(graph):
        previous = 2
        # Set order differs from distance order, exposing even a one-ULP drift.
        for node in (8, 3, 12, 4, 11, 5, 10, 6, 9, 7):
            graph.add_edge(node, previous)
            previous = node
            yield node
        if remove_target:
            graph.remove_node(1)

    if remove_target:
        # A removed target becomes a BFS root when NetworkX transposes: its
        # NodeNotFound is observable, rather than a silently retained zero.
        with pytest.raises(nx.NodeNotFound) as expected:
            nx.harmonic_centrality(ng, sources=growing_sources(ng))
        with pytest.raises(fnx.NodeNotFound) as actual:
            fnx.harmonic_centrality(fg, sources=growing_sources(fg))
        assert actual.value.args == expected.value.args
    else:
        expected = nx.harmonic_centrality(ng, sources=growing_sources(ng))
        actual = fnx.harmonic_centrality(fg, sources=growing_sources(fg))
        assert _centrality_items_exact(actual) == _centrality_items_exact(expected)
        assert set(actual) == {0, 1, 2}, "new source nodes are not result targets"


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_harmonic_source_subset_lazy_deleted_root(graph_type):
    """A source admitted before removal must still raise when BFS reaches it."""
    errors = []
    for lib in (fnx, nx):
        graph = getattr(lib, graph_type)([(0, 1), (1, 2)])

        def sources():
            yield 0
            graph.remove_node(0)

        with pytest.raises(lib.NodeNotFound) as error:
            lib.harmonic_centrality(graph, sources=sources())
        errors.append(error.value.args)
    assert errors[0] == errors[1]


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("seed", range(6))
@pytest.mark.parametrize("provenance", ["direct", "touched", "copy", "filtered"])
def test_harmonic_target_source_exact(graph_type, seed, provenance):
    """Both sides of the transpose threshold retain exact accumulation order."""
    nodes = [1, "root", ("pair", 2), -2, 5, 7, 11, "isolated"]
    graphs = [getattr(lib, graph_type)() for lib in (fnx, nx)]
    rng = random.Random(seed)
    edges = [(u, v) for u in nodes[:-1] for v in nodes[:-1] if rng.random() < .25]
    for graph in graphs:
        graph.add_nodes_from(nodes)
        graph.add_edges_from(edges)
        if graph.is_multigraph():
            graph.add_edges_from(edges)
        if provenance == "touched":
            list(graph.nodes(data=True))
            list(graph.edges(data=True))
    if provenance == "copy":
        graphs = [graph.copy() for graph in graphs]
    elif provenance == "filtered":
        graphs = [graph.subgraph(nodes[:-2]) for graph in graphs]
    fg, ng = graphs
    # Transposed, forward, equal-size, scalar/alias, unknown and empty bunches.
    for targets, sources in (([1, "root"], nodes), (nodes, [1, "root"]),
                             (nodes[::2], nodes[1::2]), (True, [1.0, "root"]),
                             (["missing", "isolated"], ["unknown", 1]), ([], nodes)):
        expected = nx.harmonic_centrality(ng, nbunch=targets, sources=sources)
        actual = fnx.harmonic_centrality(fg, nbunch=targets, sources=sources)
        assert _centrality_items_exact(actual) == _centrality_items_exact(expected)
    expected = nx.harmonic_centrality(
        ng, nbunch=(u for u in nodes[:2]), sources=(u for u in nodes))
    actual = fnx.harmonic_centrality(
        fg, nbunch=(u for u in nodes[:2]), sources=(u for u in nodes))
    assert _centrality_items_exact(actual) == _centrality_items_exact(expected)


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("namespace", ["top", "algorithms", "centrality"])
def test_harmonic_target_source_reaches_copy_free_bfs(graph_type, namespace):
    """Observe the actual root BFS producer through every public entry point."""
    from franken_networkx import algorithms, centrality

    fg, ng = getattr(fnx, graph_type)(), getattr(nx, graph_type)()
    for graph in (fg, ng):
        graph.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 4), (0, 2)])
        if graph.is_multigraph():
            graph.add_edges_from([(0, 1), (2, 3)])
        graph.add_node("isolated")
    options = {"nbunch": [0, 3], "sources": list(range(5))}
    expected = nx.harmonic_centrality(ng, **options)
    entry = {"top": fnx, "algorithms": algorithms, "centrality": centrality}[namespace]
    harmonic_code = inspect.unwrap(fnx.harmonic_centrality).__code__
    lengths_code = inspect.unwrap(fnx.single_source_shortest_path_length).__code__
    forbidden_codes = {fnx._materialize_view.__code__, fnx._native_view_copy.__code__,
                       inspect.unwrap(fnx.shortest_path_length).__code__}
    consumers, roots, copies, native_calls = [], [], [], []

    def observe(frame, event, arg):
        if event == "call":
            if frame.f_code is harmonic_code:
                consumers.append(frame.f_locals["G"])
            elif frame.f_code is lengths_code:
                roots.append(frame.f_locals["G"])
            elif frame.f_code in forbidden_codes:
                copies.append(frame.f_code.co_name)
        elif event == "c_call" and arg is fnx._bfs_edges_raw:
            native_calls.append(arg.__name__)

    previous = sys.getprofile()
    try:
        sys.setprofile(observe)
        actual = entry.harmonic_centrality(fg, **options)
    finally:
        sys.setprofile(previous)
    assert _centrality_items_exact(actual) == _centrality_items_exact(expected)
    assert len(consumers) == 1 and consumers[0] is fg
    assert not copies, copies
    assert len(roots) == 2
    assert all(fnx._reverse_view_root(view) is fg for view in roots)
    assert native_calls == ["bfs_edges", "bfs_edges"]


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("kind", ["weighted", "private", "subclass"])
def test_harmonic_target_source_fallback(graph_type, kind):
    """Unsafe raw-root cases keep the real materialized/weighted producers."""
    graphs = []
    for lib in (fnx, nx):
        graph = getattr(lib, graph_type)()
        graph.add_edges_from([(0, 1, {"distance": 2}), (1, 2, {"distance": 3}),
                              (2, 3, {"distance": 4})])
        if kind == "private":
            # Python rows are authoritative and deliberately hide native edges.
            graph._succ = {u: {} for u in graph}
            graph._pred = {u: {} for u in graph}
            graph._adj = graph._succ
        elif kind == "subclass":
            graph = type("CustomDirected", (getattr(lib, graph_type),), {})(graph)
        graphs.append(graph)
    fg, ng = graphs
    options = {"nbunch": [3], "sources": [0, 1, 2, 3]}
    if kind == "weighted":
        options["distance"] = "distance"
    expected = nx.harmonic_centrality(ng, **options)
    materializations, native_calls = [], []
    materialize_code = fnx._materialize_view.__code__

    def observe(frame, event, arg):
        if event == "call" and frame.f_code is materialize_code:
            materializations.append(frame.f_code.co_name)
        elif event == "c_call" and arg is fnx._bfs_edges_raw:
            native_calls.append(arg.__name__)

    previous = sys.getprofile()
    try:
        sys.setprofile(observe)
        actual = fnx.harmonic_centrality(fg, **options)
    finally:
        sys.setprofile(previous)
    assert _centrality_items_exact(actual) == _centrality_items_exact(expected)
    assert not native_calls
    if kind == "private":
        assert not materializations, "private-root reverse views walk Python rows without materializing"
        assert _centrality_items_exact(actual) == [(3, int, 0)]
    else:
        assert materializations, "ineligible reverse roots must not leak native adjacency"


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("kind", ["empty", "singleton", "empty-selection", "unknown", "unhashable"])
def test_harmonic_target_source_boundaries(graph_type, kind):
    fg, ng = getattr(fnx, graph_type)(), getattr(nx, graph_type)()
    nodes = [] if kind == "empty" else [0] if kind == "singleton" else [0, 1, 2]
    for graph in (fg, ng):
        graph.add_nodes_from(nodes)
        if len(nodes) > 1:
            graph.add_edges_from([(0, 1), (1, 2)])
    targets, sources = nodes, nodes
    if kind == "empty-selection":
        targets, sources = [2], []
    elif kind == "unknown":
        targets, sources = [2, "missing"], [0, "unknown"]
    elif kind == "unhashable":
        targets, sources = [[]], [0]
        with pytest.raises(nx.NetworkXError) as expected:
            nx.harmonic_centrality(ng, nbunch=targets, sources=sources)
        with pytest.raises(fnx.NetworkXError) as actual:
            fnx.harmonic_centrality(fg, nbunch=targets, sources=sources)
        assert actual.value.args == expected.value.args
        return
    assert _centrality_items_exact(fnx.harmonic_centrality(fg, nbunch=targets, sources=sources)) == (
        _centrality_items_exact(nx.harmonic_centrality(ng, nbunch=targets, sources=sources)))


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("kind", ["growth", "deleted-target", "deleted-source"])
def test_harmonic_target_source_lazy_mutation(graph_type, kind):
    graphs = [getattr(lib, graph_type)([(2, 1), (1, 0)]) for lib in (fnx, nx)]

    def changing_sources(graph):
        if kind == "deleted-source":
            yield 2
            graph.remove_node(2)
            return
        previous = 2
        for node in (8, 3, 12, 4, 11, 5, 10, 6, 9, 7):
            graph.add_edge(node, previous)
            previous = node
            yield node
        if kind == "deleted-target":
            graph.remove_node(1)

    fg, ng = graphs
    if kind == "growth":
        expected = nx.harmonic_centrality(ng, nbunch=[0, 1], sources=changing_sources(ng))
        actual = fnx.harmonic_centrality(fg, nbunch=[0, 1], sources=changing_sources(fg))
        assert _centrality_items_exact(actual) == _centrality_items_exact(expected)
    else:
        with pytest.raises(nx.NodeNotFound) as expected:
            nx.harmonic_centrality(ng, nbunch=[0, 1], sources=changing_sources(ng))
        with pytest.raises(fnx.NodeNotFound) as actual:
            fnx.harmonic_centrality(fg, nbunch=[0, 1], sources=changing_sources(fg))
        assert actual.value.args == expected.value.args


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_harmonic_target_source_mutation_and_result_independence(graph_type):
    fg, ng = getattr(fnx, graph_type)(), getattr(nx, graph_type)()
    for graph in (fg, ng):
        graph.add_edges_from([(0, 1), (1, 2), (2, 3)])
        graph.add_node("isolated")
    options = {"nbunch": [3, "isolated"], "sources": [0, 1, 2, 3]}
    for step in range(3):
        snapshot = (list(fg), list(fg.edges(keys=True) if fg.is_multigraph() else fg.edges()))
        expected = nx.harmonic_centrality(ng, **options)
        actual = fnx.harmonic_centrality(fg, **options)
        assert _centrality_items_exact(actual) == _centrality_items_exact(expected)
        assert snapshot == (list(fg), list(fg.edges(keys=True) if fg.is_multigraph() else fg.edges()))
        actual[3] = "caller changed result"
        assert _centrality_items_exact(fnx.harmonic_centrality(fg, **options)) == (
            _centrality_items_exact(expected))
        for graph in (fg, ng):
            if step == 0:
                graph.remove_edge(1, 2)
            elif step == 1:
                graph.add_edge(0, 3)


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
def test_harmonic_target_source_caller_alias_key_identity(graph_type):
    fg, ng = getattr(fnx, graph_type)(), getattr(nx, graph_type)()
    for graph in (fg, ng):
        graph.add_edges_from([(0, 1), (2, 1), (3, 2)])
    options = {"nbunch": [True], "sources": [0, 1.0, 2, 3]}
    expected = nx.harmonic_centrality(ng, **options)
    actual = fnx.harmonic_centrality(fg, **options)
    assert _centrality_items_exact(actual) == _centrality_items_exact(expected)
    assert next(iter(actual)) is True
    assert next(iter(expected)) is True


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("namespace", ["top", "algorithms", "centrality"])
@pytest.mark.parametrize("layout", ["forward", "equal"])
def test_harmonic_target_source_batch_reaches_guarded_producer(graph_type, namespace, layout):
    """Observe the reducer join or the projection-free multigraph producer."""
    from franken_networkx import algorithms, centrality

    fg, ng = getattr(fnx, graph_type)(), getattr(nx, graph_type)()
    for graph in (fg, ng):
        graph.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 4), (0, 2)])
        if graph.is_multigraph():
            graph.add_edges_from([(0, 1), (2, 3)])
        graph.add_node("isolated")
    targets = [True, 2] if layout == "equal" else [True, 2, 3, 4, "isolated"]
    options = {"nbunch": targets, "sources": [0, 2]}
    expected = nx.harmonic_centrality(ng, **options)
    entry = {"top": fnx, "algorithms": algorithms, "centrality": centrality}[namespace]
    harmonic_code = inspect.unwrap(fnx.harmonic_centrality).__code__
    forbidden_codes = {fnx._materialize_view.__code__, fnx._native_view_copy.__code__,
                       inspect.unwrap(fnx.shortest_path_length).__code__}
    lengths_code = inspect.unwrap(fnx.single_source_shortest_path_length).__code__
    consumers, other_calls, native_calls, lengths, native_lengths = [], [], [], [], []

    def observe(frame, event, arg):
        if event == "call":
            if frame.f_code is harmonic_code:
                consumers.append(frame.f_locals["G"])
            elif frame.f_code is lengths_code:
                lengths.append(frame.f_locals["G"])
            elif frame.f_code in forbidden_codes:
                other_calls.append(frame.f_code.co_name)
        elif event == "c_call" and arg is fnx._raw_harmonic_centrality:
            native_calls.append(arg.__name__)
        elif event == "c_call" and arg is fnx._raw_single_source_shortest_path_length:
            native_lengths.append(arg.__name__)

    previous = sys.getprofile()
    try:
        sys.setprofile(observe)
        actual = entry.harmonic_centrality(fg, **options)
    finally:
        sys.setprofile(previous)
    assert _centrality_items_exact(actual) == _centrality_items_exact(expected)
    assert len(consumers) == 1 and consumers[0] is fg
    assert not other_calls, other_calls
    if fg.is_multigraph():
        assert not native_calls
        assert len(lengths) == 2 and all(graph is fg for graph in lengths)
        assert native_lengths == ["single_source_shortest_path_length"] * 2
    else:
        assert native_calls == ["harmonic_centrality"]
        assert not lengths and not native_lengths
    assert next(key for key in actual if key == 1) is True
    assert actual != nx.harmonic_centrality(ng, nbunch=targets), "sources must not be dropped"


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("kind", ["private", "subclass"])
def test_harmonic_target_source_batch_fallback(graph_type, kind):
    graphs = []
    for lib in (fnx, nx):
        graph = getattr(lib, graph_type)([(0, 1), (1, 2), (2, 3)])
        if kind == "private":
            rows = {u: {} for u in graph}
            graph._adj = rows
            if graph.is_directed():
                graph._succ = rows
                graph._pred = {u: {} for u in graph}
        else:
            graph = type("CustomGraph", (getattr(lib, graph_type),), {})(graph)
        graphs.append(graph)
    fg, ng = graphs
    expected = nx.harmonic_centrality(ng, nbunch=[1, 2, 3], sources=[0])
    lengths_code = inspect.unwrap(fnx.single_source_shortest_path_length).__code__
    lengths, native_calls = [], []

    def observe(frame, event, arg):
        if event == "call" and frame.f_code is lengths_code:
            lengths.append(frame.f_code.co_name)
        elif event == "c_call" and arg is fnx._raw_harmonic_centrality:
            native_calls.append(arg.__name__)

    previous = sys.getprofile()
    try:
        sys.setprofile(observe)
        actual = fnx.harmonic_centrality(fg, nbunch=[1, 2, 3], sources=[0])
    finally:
        sys.setprofile(previous)
    assert _centrality_items_exact(actual) == _centrality_items_exact(expected)
    assert len(lengths) == 1
    assert not native_calls
    if kind == "private":
        assert all(type(score) is int and score == 0 for score in actual.values())


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("kind", ["empty", "empty-sources", "unknown-sources", "empty-targets"])
def test_harmonic_target_source_batch_no_traversal(graph_type, kind):
    fg, ng = getattr(fnx, graph_type)(), getattr(nx, graph_type)()
    if kind != "empty":
        fg.add_node("alone")
        ng.add_node("alone")
    targets = [] if kind == "empty-targets" else ["alone"]
    sources = ["alone"] if kind == "empty-targets" else ["missing"] if kind == "unknown-sources" else []
    expected = nx.harmonic_centrality(ng, nbunch=targets, sources=sources)
    lengths_code = inspect.unwrap(fnx.single_source_shortest_path_length).__code__
    calls = []

    def observe(frame, event, arg):
        if event == "call" and frame.f_code is lengths_code:
            calls.append("lengths")
        elif event == "c_call" and arg is fnx._raw_harmonic_centrality:
            calls.append("harmonic")

    previous = sys.getprofile()
    try:
        sys.setprofile(observe)
        actual = fnx.harmonic_centrality(fg, nbunch=targets, sources=sources)
    finally:
        sys.setprofile(previous)
    assert _centrality_items_exact(actual) == _centrality_items_exact(expected)
    assert not calls


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("kind", ["growth", "deleted-target", "deleted-source"])
def test_harmonic_target_source_batch_lazy_mutation(graph_type, kind):
    graphs = [getattr(lib, graph_type)([(0, 1), (1, 2), (2, 3)]) for lib in (fnx, nx)]

    def changing_sources(graph):
        yield 0
        if kind == "deleted-source":
            graph.remove_node(0)
        elif kind == "deleted-target":
            graph.remove_node(3)
        else:
            graph.add_edge(4, 0)
            yield 4

    fg, ng = graphs
    if kind == "deleted-source":
        with pytest.raises(nx.NodeNotFound) as expected:
            nx.harmonic_centrality(ng, nbunch=[1, 2, 3], sources=changing_sources(ng))
        with pytest.raises(fnx.NodeNotFound) as actual:
            fnx.harmonic_centrality(fg, nbunch=[1, 2, 3], sources=changing_sources(fg))
        assert actual.value.args == expected.value.args
    else:
        expected = nx.harmonic_centrality(ng, nbunch=[1, 2, 3], sources=changing_sources(ng))
        actual = fnx.harmonic_centrality(fg, nbunch=[1, 2, 3], sources=changing_sources(fg))
        assert _centrality_items_exact(actual) == _centrality_items_exact(expected)
        if kind == "deleted-target":
            assert actual[3] == 0 and type(actual[3]) is int
        else:
            assert set(actual) == {1, 2, 3}, "new source must not become a target"


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_harmonic_target_source_batch_mutation_and_independence(graph_type):
    fg, ng = getattr(fnx, graph_type)([(0, 1), (1, 2), (2, 3)]), getattr(nx, graph_type)([(0, 1), (1, 2), (2, 3)])
    options = {"nbunch": [True, 2, 3], "sources": [0, 2.0]}
    for step in range(3):
        snapshot = (list(fg), list(fg.edges(keys=True) if fg.is_multigraph() else fg.edges()))
        expected = nx.harmonic_centrality(ng, **options)
        actual = fnx.harmonic_centrality(fg, **options)
        assert _centrality_items_exact(actual) == _centrality_items_exact(expected)
        assert snapshot == (list(fg), list(fg.edges(keys=True) if fg.is_multigraph() else fg.edges()))
        assert next(key for key in actual if key == 1) is True
        actual[True] = "caller changed result"
        assert _centrality_items_exact(fnx.harmonic_centrality(fg, **options)) == _centrality_items_exact(expected)
        for graph in (fg, ng):
            if step == 0:
                graph.remove_edge(1, 2)
            elif step == 1:
                graph.add_edge(0, 3)


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_harmonic_target_source_batch_lazy_private_storage(graph_type):
    graphs = [getattr(lib, graph_type)([(0, 1), (1, 2)]) for lib in (fnx, nx)]

    def sources(graph):
        # Eligibility must be tested after consuming the source iterable.
        rows = {u: {} for u in graph}
        graph._adj = rows
        if graph.is_directed():
            graph._succ = rows
            graph._pred = {u: {} for u in graph}
        yield 0

    fg, ng = graphs
    expected = nx.harmonic_centrality(ng, nbunch=[1, 2], sources=sources(ng))
    actual = fnx.harmonic_centrality(fg, nbunch=[1, 2], sources=sources(fg))
    assert _centrality_items_exact(actual) == _centrality_items_exact(expected)
    assert all(type(score) is int and score == 0 for score in actual.values())


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("cutoff", [None, 0, 1, 2, -1, .5, 1.5, float("inf"), float("nan")])
def test_harmonic_target_source_batch_private_lengths(graph_type, cutoff):
    """The fallback producer reads live Python rows, not hidden native edges."""
    graphs = []
    for lib in (fnx, nx):
        graph = getattr(lib, graph_type)([(0, 1), (1, 2), (2, 3)])
        graph.add_node("isolated")
        rows = {0: {2: {}, 1: {}}, 1: {3: {}}, 2: {3: {}}, 3: {}, "isolated": {}}
        graph._adj = rows
        if graph.is_directed():
            graph._succ = rows
            graph._pred = {u: {} for u in graph}
        graphs.append(graph)
    fg, ng = graphs
    native_calls = []

    def observe(frame, event, arg):
        if event == "c_call" and arg is fnx._raw_single_source_shortest_path_length:
            native_calls.append(arg.__name__)

    previous = sys.getprofile()
    try:
        sys.setprofile(observe)
        actual = fnx.single_source_shortest_path_length(fg, False, cutoff=cutoff)
    finally:
        sys.setprofile(previous)
    expected = nx.single_source_shortest_path_length(ng, False, cutoff=cutoff)
    assert list(actual.items()) == list(expected.items())
    assert next(iter(actual)) is False and next(iter(expected)) is False
    assert not native_calls
    for graph in graphs:
        graph._adj[0].clear()
    assert list(fnx.single_source_shortest_path_length(fg, 0).items()) == list(
        nx.single_source_shortest_path_length(ng, 0).items()) == [(0, 0)]


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("kind", ["missing-source", "missing-row", "extra-row"])
def test_harmonic_target_source_batch_private_length_boundaries(graph_type, kind):
    graphs = []
    for lib in (fnx, nx):
        graph = getattr(lib, graph_type)([(0, 1), (1, 2), (2, 3)])
        rows = {0: {2: {}}, 1: {}, 2: {3: {}}, 3: {}}
        if kind == "missing-row":
            rows.pop(2)
        elif kind == "extra-row":
            rows[0]["extra"] = {}
            rows["extra"] = {}
        graph._adj = rows
        if graph.is_directed():
            graph._succ = rows
            graph._pred = {u: {} for u in graph}
        graphs.append(graph)
    fg, ng = graphs
    source = "absent" if kind == "missing-source" else 0
    if kind == "extra-row":
        assert list(fnx.single_source_shortest_path_length(fg, source).items()) == list(
            nx.single_source_shortest_path_length(ng, source).items())
    else:
        error_type = KeyError if kind == "missing-row" else nx.NodeNotFound
        with pytest.raises(error_type) as expected:
            nx.single_source_shortest_path_length(ng, source)
        error_type = KeyError if kind == "missing-row" else fnx.NodeNotFound
        with pytest.raises(error_type) as actual:
            fnx.single_source_shortest_path_length(fg, source)
        assert actual.value.args == expected.value.args


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("kind", ["default", "sources-only", "targets-only", "lazy-sources-only"])
def test_harmonic_target_source_batch_private_public_variants(graph_type, kind):
    """Positive private edges must remain authoritative in every unweighted arm."""
    graphs = [getattr(lib, graph_type)([(0, 1), (1, 2), (2, 3)]) for lib in (fnx, nx)]

    def assign_rows(graph):
        rows = {0: {2: {}, 1: {}}, 1: {3: {}}, 2: {3: {}}, 3: {}, "isolated": {}}
        if not graph.is_directed():
            rows[1][0] = {}
            rows[2][0] = {}
            rows[3].update({1: {}, 2: {}})
        if graph.is_multigraph():
            rows = {u: {v: {"key": attrs} for v, attrs in neighbors.items()}
                    for u, neighbors in rows.items()}
        graph._adj = rows
        if graph.is_directed():
            graph._succ = rows
            pred = {u: {} for u in rows}
            for u, neighbors in rows.items():
                for v, attrs in neighbors.items():
                    pred[v][u] = attrs
            graph._pred = pred

    def changing_sources(graph):
        assign_rows(graph)
        yield 0

    for graph in graphs:
        graph.add_node("isolated")
        if kind != "lazy-sources-only":
            assign_rows(graph)
    options = {}
    if kind == "sources-only":
        options["sources"] = [0]
    elif kind == "targets-only":
        options["nbunch"] = [3, "isolated"]
    fg, ng = graphs
    expected_options = dict(options)
    if kind == "lazy-sources-only":
        options["sources"] = changing_sources(fg)
        expected_options["sources"] = changing_sources(ng)
    expected = nx.harmonic_centrality(ng, **expected_options)
    native_calls = []

    def observe(frame, event, arg):
        if event == "c_call" and arg is fnx._raw_harmonic_centrality:
            native_calls.append(arg.__name__)

    previous = sys.getprofile()
    try:
        sys.setprofile(observe)
        actual = fnx.harmonic_centrality(fg, **options)
    finally:
        sys.setprofile(previous)
    assert _centrality_items_exact(actual) == _centrality_items_exact(expected)
    assert actual["isolated"] == 0 and type(actual["isolated"]) is int
    assert any(score > 0 for score in actual.values()), "positive private rows must be exercised"
    assert not native_calls
