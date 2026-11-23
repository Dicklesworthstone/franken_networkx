"""Conformance for Google/PageRank matrix arithmetic and provider ordering.

Compare public results with the NetworkX oracle, including vector domains,
dangling-row normalization, node selection and observable provider failures.
The ordinary dense builder remains owned by FrankenNetworkX.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx

np = pytest.importorskip("numpy")


def _wg(cls, seed):
    r = random.Random(seed)
    n = r.randint(5, 10)
    fg, ng = cls(), getattr(nx, cls.__name__)()
    fg.add_nodes_from(range(n)); ng.add_nodes_from(range(n))
    directed = fg.is_directed()
    for u in range(n):
        for v in range(n):
            if u != v and (directed or u < v) and r.random() < 0.4:
                w = r.randint(1, 5)
                fg.add_edge(u, v, weight=w); ng.add_edge(u, v, weight=w)
    return fg, ng, n


@pytest.mark.parametrize("cls", [fnx.Graph, fnx.DiGraph])
@pytest.mark.parametrize("alpha", [0.5, 0.85, 0.9])
@pytest.mark.parametrize("seed", range(8))
def test_default_case_routed_matches_nx(cls, alpha, seed):
    fg, ng, n = _wg(cls, seed)
    a = np.asarray(fnx.google_matrix(fg, alpha=alpha), dtype=float)
    b = np.asarray(nx.google_matrix(ng, alpha=alpha), dtype=float)
    assert a.shape == b.shape and np.allclose(a, b, atol=1e-9)


@pytest.mark.parametrize("seed", range(8))
def test_personalization_with_dangling_node(seed):
    # br-r37-c1-gmdangling: a dangling node's mass must redistribute using the
    # PERSONALIZATION vector (not uniform 1/n) when no explicit dangling is given.
    # Build a graph guaranteed to have a dangling node + non-uniform personalization.
    r = random.Random(seed + 100)
    n = r.randint(5, 9)
    fg, ng = fnx.DiGraph(), nx.DiGraph()
    fg.add_nodes_from(range(n)); ng.add_nodes_from(range(n))
    for u in range(n - 1):                       # node n-1 left dangling
        for v in range(n):
            if u != v and r.random() < 0.5:
                fg.add_edge(u, v); ng.add_edge(u, v)
    p = {i: (i + 1) for i in range(n)}           # non-uniform personalization
    assert np.allclose(np.asarray(fnx.google_matrix(fg, personalization=p), dtype=float),
                       np.asarray(nx.google_matrix(ng, personalization=p), dtype=float), atol=1e-9)


def test_non_default_paths_match_nx():
    fg, ng, n = _wg(fnx.DiGraph, 1)
    nodes = list(range(n))
    # personalization (no dangling node in this graph).
    p = {i: (i + 1) for i in nodes}
    if all(fg.out_degree(i) > 0 for i in range(n)):
        assert np.allclose(np.asarray(fnx.google_matrix(fg, personalization=p), dtype=float),
                           np.asarray(nx.google_matrix(ng, personalization=p), dtype=float), atol=1e-9)
    # dangling
    d = {nodes[-1]: 1.0}
    assert np.allclose(np.asarray(fnx.google_matrix(fg, dangling=d), dtype=float),
                       np.asarray(nx.google_matrix(ng, dangling=d), dtype=float), atol=1e-9)
    # custom nodelist (reversed)
    rl = list(reversed(nodes))
    assert np.allclose(np.asarray(fnx.google_matrix(fg, nodelist=rl), dtype=float),
                       np.asarray(nx.google_matrix(ng, nodelist=rl), dtype=float), atol=1e-9)
    # weight=None
    assert np.allclose(np.asarray(fnx.google_matrix(fg, weight=None), dtype=float),
                       np.asarray(nx.google_matrix(ng, weight=None), dtype=float), atol=1e-9)


def test_dangling_node_routed():
    fg = fnx.DiGraph([(0, 1), (1, 2)]); fg.add_node(3)
    ng = nx.DiGraph([(0, 1), (1, 2)]); ng.add_node(3)
    assert np.allclose(np.asarray(fnx.google_matrix(fg), dtype=float),
                       np.asarray(nx.google_matrix(ng), dtype=float), atol=1e-9)


_MATRIX_GRAPH_CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _matrix_domain_graph(module, class_name, *, has_dangling=True):
    graph = getattr(module, class_name)()
    graph.add_nodes_from(range(3))
    graph.add_weighted_edges_from([(0, 1, 2), (1, 0, 3)])
    if not has_dangling:
        graph.add_weighted_edges_from([(1, 2, 4), (2, 0, 5)])
    return graph


def _assert_google_matrix_outcome(
    graph, reference, kwargs, *, floating_errors="ignore"
):
    """Compare the matrix or exception against the live NetworkX oracle."""
    with np.errstate(
        divide=floating_errors, invalid=floating_errors, over=floating_errors
    ):
        try:
            expected = nx.google_matrix(reference, **kwargs)
        except Exception as expected_error:
            with pytest.raises(type(expected_error)) as actual_error:
                fnx.google_matrix(graph, **kwargs)
            assert str(actual_error.value) == str(expected_error)
        else:
            actual = fnx.google_matrix(graph, **kwargs)
            np.testing.assert_array_equal(actual, expected)
            assert actual.dtype == expected.dtype


_MATRIX_VECTOR_CASES = [
    pytest.param({}, id="uniform"),
    pytest.param({"personalization": {}}, id="empty-personalization"),
    pytest.param(
        {"personalization": {0: 1, 1: -1}}, id="cancelling-personalization"
    ),
    pytest.param(
        {"personalization": {0: -1, 1: -4, 2: -1}},
        id="negative-personalization",
    ),
    pytest.param(
        {"personalization": {0: 2, 1: -4, 2: 1}},
        id="mixed-personalization",
    ),
    pytest.param(
        {"personalization": {0: float("nan"), 1: 1}},
        id="nan-personalization",
    ),
    pytest.param(
        {"personalization": {0: float("inf"), 1: 1}},
        id="infinite-personalization",
    ),
    pytest.param({"dangling": {}}, id="empty-dangling"),
    pytest.param({"dangling": {0: 1, 1: -1}}, id="cancelling-dangling"),
    pytest.param(
        {"dangling": {0: -1, 1: -4, 2: -1}}, id="negative-dangling"
    ),
    pytest.param(
        {"dangling": {0: float("nan"), 1: 1}}, id="nan-dangling"
    ),
    pytest.param(
        {"dangling": {0: float("inf"), 1: 1}}, id="infinite-dangling"
    ),
    pytest.param(
        {"personalization": {0: np.float32(0.1), 1: np.float32(0.4), 2: "0.1"}},
        id="vector-float-conversion",
    ),
    pytest.param(
        {
            "personalization": {0: 1, 1: 4, 2: 1},
            "dangling": {0: 4, 1: 1, 2: 1},
            "alpha": np.float32(0.75),
        },
        id="both-vectors",
    ),
]


@pytest.mark.parametrize("class_name", _MATRIX_GRAPH_CLASSES)
@pytest.mark.parametrize("kwargs", _MATRIX_VECTOR_CASES)
def test_google_matrix_vector_domains_match_networkx(class_name, kwargs):
    graph = _matrix_domain_graph(fnx, class_name)
    reference = _matrix_domain_graph(nx, class_name)
    _assert_google_matrix_outcome(graph, reference, kwargs)


@pytest.mark.parametrize("class_name", _MATRIX_GRAPH_CLASSES)
@pytest.mark.parametrize("vector", ["personalization", "dangling"])
def test_google_matrix_normalizes_positive_dangling_rows_exactly(class_name, vector):
    # The normalized [1, 4, 1] vector sums to 0.9999999999999999.
    # alpha=1 exposes the final row normalization without teleport rounding.
    graph = _matrix_domain_graph(fnx, class_name)
    reference = _matrix_domain_graph(nx, class_name)
    _assert_google_matrix_outcome(
        graph, reference, {vector: {0: 1.0, 1: 4.0, 2: 1.0}, "alpha": 1.0}
    )


@pytest.mark.parametrize("class_name", _MATRIX_GRAPH_CLASSES)
@pytest.mark.parametrize(
    "empty, kwargs",
    [
        pytest.param(True, {}, id="empty-default"),
        pytest.param(True, {"nodelist": []}, id="empty-selection"),
        pytest.param(True, {"nodelist": [0]}, id="empty-invalid-selection"),
        pytest.param(False, {"nodelist": [2, 0, 1]}, id="reordered"),
        pytest.param(False, {"nodelist": [0, 1]}, id="subset-no-dangling"),
        pytest.param(False, {"nodelist": [0, 2]}, id="subset-dangling"),
        pytest.param(False, {"nodelist": []}, id="nonempty-empty-selection"),
        pytest.param(False, {"nodelist": [0, 0, 1]}, id="duplicate-selection"),
        pytest.param(False, {"nodelist": [99]}, id="missing-selection"),
        pytest.param(
            False,
            {"nodelist": [0, 1], "personalization": {0: 1, 1: 2}},
            id="subset-explicit-vector",
        ),
        pytest.param(
            False, {"nodelist": [], "personalization": {}},
            id="empty-selection-explicit-vector",
        ),
    ],
)
def test_google_matrix_selection_and_empty_graph_order(class_name, empty, kwargs):
    graph = getattr(fnx, class_name)() if empty else _matrix_domain_graph(fnx, class_name)
    reference = getattr(nx, class_name)() if empty else _matrix_domain_graph(nx, class_name)
    _assert_google_matrix_outcome(graph, reference, kwargs)


@pytest.mark.parametrize("class_name", _MATRIX_GRAPH_CLASSES)
@pytest.mark.parametrize("has_dangling", [False, True])
def test_google_matrix_preserves_numpy_errors_for_explicit_dangling(
    class_name, has_dangling
):
    # An explicit vector is normalized even when no graph row needs it.
    graph = _matrix_domain_graph(fnx, class_name, has_dangling=has_dangling)
    reference = _matrix_domain_graph(nx, class_name, has_dangling=has_dangling)
    _assert_google_matrix_outcome(
        graph, reference, {"dangling": {}}, floating_errors="raise"
    )


@pytest.mark.parametrize("class_name", _MATRIX_GRAPH_CLASSES)
@pytest.mark.parametrize("nodelist", [None, [2, 0, 1]])
def test_google_matrix_vector_callbacks_follow_matrix_capture(class_name, nodelist):
    outcomes = []
    for module in (fnx, nx):
        graph = _matrix_domain_graph(module, class_name)
        events = []

        class Provider:
            def __init__(self, name):
                self.name = name
                self.first = True

            def get(self, node, default):
                events.append((self.name, node))
                if self.first:
                    self.first = False
                    if self.name == "personalization":
                        graph.add_edge(2, 0, weight=13)
                        graph.add_node(3)
                    else:
                        graph.add_edge(1, 2, weight=7)
                return {0: 1, 1: 4, 2: 1, 3: 99}.get(node, default)

        matrix = module.google_matrix(
            graph,
            nodelist=nodelist,
            personalization=Provider("personalization"),
            dangling=Provider("dangling"),
        )
        edges = list(
            graph.edges(keys=True, data=True)
            if graph.is_multigraph() else graph.edges(data=True)
        )
        outcomes.append((matrix, events, list(graph), edges))

    np.testing.assert_array_equal(outcomes[0][0], outcomes[1][0])
    assert outcomes[0][0].shape == (3, 3)
    assert outcomes[0][1:] == outcomes[1][1:]
    order = [0, 1, 2] if nodelist is None else nodelist
    assert outcomes[0][1] == [
        (name, node) for name in ("personalization", "dangling") for node in order
    ]


@pytest.mark.parametrize("class_name", _MATRIX_GRAPH_CLASSES)
@pytest.mark.parametrize("failure", ["node-selection", "personalization"])
def test_google_matrix_failures_precede_later_vector_providers(class_name, failure):
    class ForbiddenProvider:
        def get(self, node, default):
            raise AssertionError("a later vector provider was consumed")

    graph = _matrix_domain_graph(fnx, class_name)
    reference = _matrix_domain_graph(nx, class_name)
    kwargs = (
        {"nodelist": [99], "personalization": ForbiddenProvider()}
        if failure == "node-selection"
        else {"personalization": {}, "dangling": ForbiddenProvider()}
    )
    _assert_google_matrix_outcome(graph, reference, kwargs)


@pytest.mark.parametrize("class_name", _MATRIX_GRAPH_CLASSES)
def test_google_matrix_default_order_uses_graph_iteration(class_name):
    outcomes = []
    for module in (fnx, nx):
        class ReversedIterationGraph(getattr(nx, class_name)):
            def __iter__(self):
                return iter(reversed(list(super().__iter__())))

        graph = ReversedIterationGraph()
        graph.add_nodes_from(range(3))
        graph.add_weighted_edges_from([(0, 1, 2), (1, 2, 5)])
        assert list(graph.nodes()) == [0, 1, 2]
        assert list(graph) == [2, 1, 0]
        outcomes.append(module.google_matrix(graph))
    np.testing.assert_array_equal(outcomes[0], outcomes[1])
