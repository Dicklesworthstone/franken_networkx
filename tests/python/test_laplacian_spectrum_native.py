import numpy as np
import networkx as nx
import pytest
import franken_networkx as fnx


@pytest.mark.parametrize(
    "fn_name",
    ["directed_laplacian_matrix", "directed_combinatorial_laplacian_matrix"],
)
@pytest.mark.parametrize(
    "fnx_cls,nx_cls",
    [
        (fnx.Graph, nx.Graph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_directed_laplacian_guard_order_matches_networkx(fn_name, fnx_cls, nx_cls):
    Gf = fnx_cls([(0, 1)])
    Gn = nx_cls([(0, 1)])

    with pytest.raises(nx.NetworkXNotImplemented) as fnx_exc:
        getattr(fnx, fn_name)(Gf)
    with pytest.raises(nx.NetworkXNotImplemented) as nx_exc:
        getattr(nx, fn_name)(Gn)

    assert str(fnx_exc.value) == str(nx_exc.value)


def test_unweighted_complete_laplacian_closed_form_matches_nx_sorted_values():
    Gf = fnx.complete_graph(31)
    Gn = nx.complete_graph(31)
    fr = fnx.laplacian_spectrum(Gf)
    nr = nx.laplacian_spectrum(Gn)
    expected = np.empty(31, dtype=np.float64)
    expected[0] = 0.0
    expected[1:] = 31.0
    assert fr.dtype == np.float64
    assert np.allclose(np.sort(fr), np.sort(nr))
    assert np.allclose(fr, expected)


def test_weighted_complete_laplacian_stays_on_weighted_route():
    Gf = fnx.complete_graph(7)
    Gn = nx.complete_graph(7)
    Gf[0][1]["weight"] = 2.5
    Gn[0][1]["weight"] = 2.5
    fr = fnx.laplacian_spectrum(Gf)
    nr = nx.laplacian_spectrum(Gn)
    unweighted = np.empty(7, dtype=np.float64)
    unweighted[0] = 0.0
    unweighted[1:] = 7.0
    assert fr.dtype == np.float64
    assert np.allclose(np.sort(fr), np.sort(nr))
    assert not np.allclose(np.sort(fr), unweighted)


def test_unweighted_star_laplacian_closed_form_matches_nx_sorted_values():
    assert fnx._star_laplacian_spectrum_sorted_value_safe(fnx.empty_graph(1), None) is None
    assert np.allclose(
        fnx._star_laplacian_spectrum_sorted_value_safe(fnx.star_graph(1), None),
        np.asarray([0.0, 2.0], dtype=np.float64),
    )
    for leaves in (1, 30):
        Gf = fnx.star_graph(leaves)
        Gn = nx.star_graph(leaves)
        fr = fnx.laplacian_spectrum(Gf)
        nr = nx.laplacian_spectrum(Gn)
        n = leaves + 1
        expected = np.ones(n, dtype=np.float64)
        expected[0] = 0.0
        expected[-1] = float(n)
        assert fr.dtype == np.float64
        assert np.allclose(np.sort(fr), np.sort(nr))
        assert np.allclose(fr, expected)


def test_unweighted_star_laplacian_uses_shape_certificate():
    Gf = fnx.star_graph(30)
    assert vars(Gf)["_fnx_star_shape"] == (Gf.nodes_seq, Gf.edges_seq, 31)
    assert fnx._star_shape_certificate_size(Gf, "weight") == 31
    assert fnx._star_shape_certificate_size(Gf, None) == 31
    expected = np.ones(31, dtype=np.float64)
    expected[0] = 0.0
    expected[-1] = 31.0
    assert np.allclose(fnx.laplacian_spectrum(Gf), expected)


def test_weighted_star_laplacian_stays_on_weighted_route():
    Gf = fnx.star_graph(8)
    Gn = nx.star_graph(8)
    Gf[0][1]["weight"] = 2.5
    Gn[0][1]["weight"] = 2.5
    fr = fnx.laplacian_spectrum(Gf)
    nr = nx.laplacian_spectrum(Gn)
    assert fnx._star_laplacian_spectrum_sorted_value_safe(Gf, "weight") is None
    assert fr.dtype == np.float64
    assert np.allclose(np.sort(fr), np.sort(nr))


def test_star_laplacian_certificate_rejects_existing_edge_weight_update():
    Gf = fnx.star_graph(8)
    Gn = nx.star_graph(8)
    original_shape = vars(Gf)["_fnx_star_shape"]
    Gf.add_edge(0, 1, weight=3.0)
    Gn.add_edge(0, 1, weight=3.0)
    assert vars(Gf)["_fnx_star_shape"] == original_shape
    assert Gf.edges_seq != original_shape[1]
    assert fnx._star_shape_certificate_size(Gf, "weight") is None
    fr = fnx.laplacian_spectrum(Gf)
    nr = nx.laplacian_spectrum(Gn)
    unweighted = np.ones(9, dtype=np.float64)
    unweighted[0] = 0.0
    unweighted[-1] = 9.0
    assert np.allclose(np.sort(fr), np.sort(nr))
    assert not np.allclose(np.sort(fr), unweighted)


def test_star_laplacian_certificate_rejects_dirty_edge_weight_mutation():
    Gf = fnx.star_graph(8)
    Gn = nx.star_graph(8)
    Gf[0][1]["weight"] = 3.0
    Gn[0][1]["weight"] = 3.0
    assert fnx._star_shape_certificate_size(Gf, "weight") is None
    fr = fnx.laplacian_spectrum(Gf)
    nr = nx.laplacian_spectrum(Gn)
    assert np.allclose(np.sort(fr), np.sort(nr))


def test_star_laplacian_certificate_keeps_weight_none_after_attrs():
    Gf = fnx.star_graph(8)
    Gn = nx.star_graph(8)
    Gf[0][1]["weight"] = 3.0
    Gn[0][1]["weight"] = 3.0
    assert fnx._star_shape_certificate_size(Gf, None) == 9
    fr = fnx.laplacian_spectrum(Gf, weight=None)
    nr = nx.laplacian_spectrum(Gn, weight=None)
    expected = np.ones(9, dtype=np.float64)
    expected[0] = 0.0
    expected[-1] = 9.0
    assert np.allclose(np.sort(fr), np.sort(nr))
    assert np.allclose(fr, expected)


def test_star_laplacian_certificate_rejects_count_preserving_rewire():
    Gf = fnx.star_graph(8)
    Gn = nx.star_graph(8)
    original_shape = vars(Gf)["_fnx_star_shape"]
    Gf.remove_edge(0, 1)
    Gn.remove_edge(0, 1)
    Gf.add_edge(1, 2)
    Gn.add_edge(1, 2)
    assert vars(Gf)["_fnx_star_shape"] == original_shape
    assert Gf.edges_seq != original_shape[1]
    assert fnx._star_shape_certificate_size(Gf, "weight") is None
    assert fnx._star_laplacian_spectrum_sorted_value_safe(Gf, "weight") is None
    fr = fnx.laplacian_spectrum(Gf)
    nr = nx.laplacian_spectrum(Gn)
    assert fr.dtype == np.float64
    assert np.allclose(np.sort(fr), np.sort(nr))


def test_unweighted_complete_normalized_laplacian_closed_form_matches_nx():
    Gf = fnx.complete_graph(31)
    Gn = nx.complete_graph(31)
    fr = fnx.normalized_laplacian_spectrum(Gf)
    nr = nx.normalized_laplacian_spectrum(Gn)
    expected = np.empty(31, dtype=np.float64)
    expected[0] = 0.0
    expected[1:] = 31.0 / 30.0
    assert fr.dtype == np.float64
    assert np.allclose(np.sort(fr), np.sort(nr))
    assert np.allclose(fr, expected)


def test_single_node_complete_normalized_laplacian_matches_nx():
    Gf = fnx.complete_graph(1)
    Gn = nx.complete_graph(1)
    fr = fnx.normalized_laplacian_spectrum(Gf)
    nr = nx.normalized_laplacian_spectrum(Gn)
    assert fr.dtype == np.float64
    assert np.allclose(fr, nr)


def test_weighted_complete_normalized_laplacian_stays_on_weighted_route():
    Gf = fnx.complete_graph(7)
    Gn = nx.complete_graph(7)
    Gf[0][1]["weight"] = 2.5
    Gn[0][1]["weight"] = 2.5
    fr = fnx.normalized_laplacian_spectrum(Gf)
    nr = nx.normalized_laplacian_spectrum(Gn)
    unweighted = np.empty(7, dtype=np.float64)
    unweighted[0] = 0.0
    unweighted[1:] = 7.0 / 6.0
    assert fr.dtype == np.float64
    assert np.allclose(np.sort(fr), np.sort(nr))
    assert not np.allclose(np.sort(fr), unweighted)


def test_unweighted_edgeless_normalized_laplacian_closed_form_matches_nx():
    Gf = fnx.empty_graph(31)
    Gn = nx.empty_graph(31)
    fr = fnx.normalized_laplacian_spectrum(Gf)
    nr = nx.normalized_laplacian_spectrum(Gn)
    expected = np.zeros(31, dtype=np.float64)
    assert fr.dtype == np.float64
    assert np.allclose(np.sort(fr), np.sort(nr))
    assert np.allclose(fr, expected)


def test_zero_node_normalized_laplacian_keeps_nx_error():
    with pytest.raises(nx.NetworkXError):
        fnx.normalized_laplacian_spectrum(fnx.empty_graph(0))


def test_unweighted_star_normalized_laplacian_closed_form_matches_nx():
    Gf = fnx.star_graph(30)
    Gn = nx.star_graph(30)
    fr = fnx.normalized_laplacian_spectrum(Gf)
    nr = nx.normalized_laplacian_spectrum(Gn)
    expected = np.ones(31, dtype=np.float64)
    expected[0] = 0.0
    expected[-1] = 2.0
    assert fr.dtype == np.float64
    assert np.allclose(np.sort(fr), np.sort(nr))
    assert np.allclose(fr, expected)


def test_weighted_star_normalized_laplacian_stays_on_weighted_route():
    Gf = fnx.star_graph(8)
    Gn = nx.star_graph(8)
    Gf[0][1]["weight"] = 2.5
    Gn[0][1]["weight"] = 2.5
    fr = fnx.normalized_laplacian_spectrum(Gf)
    nr = nx.normalized_laplacian_spectrum(Gn)
    assert (
        fnx._star_normalized_laplacian_spectrum_sorted_value_safe(Gf, "weight")
        is None
    )
    assert fr.dtype == np.float64
    assert np.allclose(np.sort(fr), np.sort(nr))


def test_unweighted_path_normalized_laplacian_closed_form_matches_nx():
    Gf = fnx.path_graph(31)
    Gn = nx.path_graph(31)
    fr = fnx.normalized_laplacian_spectrum(Gf)
    nr = nx.normalized_laplacian_spectrum(Gn)
    expected = 1.0 - np.cos(np.pi * np.arange(31, dtype=np.float64) / 30.0)
    expected[0] = -0.0
    assert fr.dtype == np.float64
    assert np.allclose(np.sort(fr), np.sort(nr))
    assert np.allclose(fr, expected)
    actual_signbit = bool(np.signbit(fr[0]))
    expected_signbit = bool(np.signbit(expected[0]))
    if actual_signbit is not expected_signbit:
        raise AssertionError("path normalized laplacian zero sign diverged")


def test_weighted_path_normalized_laplacian_stays_on_weighted_route():
    Gf = fnx.path_graph(9)
    Gn = nx.path_graph(9)
    Gf[3][4]["weight"] = 2.5
    Gn[3][4]["weight"] = 2.5
    fr = fnx.normalized_laplacian_spectrum(Gf)
    nr = nx.normalized_laplacian_spectrum(Gn)
    assert (
        fnx._path_normalized_laplacian_spectrum_sorted_value_safe(Gf, "weight")
        is None
    )
    assert fr.dtype == np.float64
    assert np.allclose(np.sort(fr), np.sort(nr))


def test_unweighted_cycle_normalized_laplacian_closed_form_matches_nx():
    Gf = fnx.cycle_graph(31)
    Gn = nx.cycle_graph(31)
    fr = fnx.normalized_laplacian_spectrum(Gf)
    nr = nx.normalized_laplacian_spectrum(Gn)
    expected = np.sort(
        1.0 - np.cos(2.0 * np.pi * np.arange(31, dtype=np.float64) / 31.0)
    )
    assert fr.dtype == np.float64
    assert np.allclose(np.sort(fr), np.sort(nr))
    assert np.allclose(fr, expected)


def test_weighted_cycle_normalized_laplacian_stays_on_weighted_route():
    Gf = fnx.cycle_graph(9)
    Gn = nx.cycle_graph(9)
    Gf[0][1]["weight"] = 2.5
    Gn[0][1]["weight"] = 2.5
    fr = fnx.normalized_laplacian_spectrum(Gf)
    nr = nx.normalized_laplacian_spectrum(Gn)
    assert (
        fnx._cycle_normalized_laplacian_spectrum_sorted_value_safe(Gf, "weight")
        is None
    )
    assert fr.dtype == np.float64
    assert np.allclose(np.sort(fr), np.sort(nr))


def test_unweighted_complete_bipartite_normalized_laplacian_closed_form_matches_nx():
    Gf = fnx.complete_bipartite_graph(11, 13)
    Gn = nx.complete_bipartite_graph(11, 13)
    assert vars(Gf)["_fnx_complete_bipartite_shape"] == (
        Gf.nodes_seq,
        Gf.edges_seq,
        11,
        13,
    )
    fr = fnx.normalized_laplacian_spectrum(Gf)
    nr = nx.normalized_laplacian_spectrum(Gn)
    expected = np.ones(24, dtype=np.float64)
    expected[0] = 0.0
    expected[-1] = 2.0
    assert fr.dtype == np.float64
    assert np.allclose(np.sort(fr), np.sort(nr))
    assert np.allclose(fr, expected)


def test_weighted_complete_bipartite_normalized_laplacian_stays_on_weighted_route():
    Gf = fnx.complete_bipartite_graph(4, 5)
    Gn = nx.complete_bipartite_graph(4, 5)
    Gf[0][4]["weight"] = 2.5
    Gn[0][4]["weight"] = 2.5
    assert vars(Gf)["_fnx_complete_bipartite_shape"] is not None
    fr = fnx.normalized_laplacian_spectrum(Gf)
    nr = nx.normalized_laplacian_spectrum(Gn)
    assert (
        fnx._complete_bipartite_normalized_laplacian_spectrum_sorted_value_safe(
            Gf, "weight"
        )
        is None
    )
    assert fr.dtype == np.float64
    assert np.allclose(np.sort(fr), np.sort(nr))


def test_complete_bipartite_normalized_laplacian_rejects_count_preserving_rewire():
    Gf = fnx.complete_bipartite_graph(4, 5)
    Gn = nx.complete_bipartite_graph(4, 5)
    original_shape = vars(Gf)["_fnx_complete_bipartite_shape"]
    Gf.remove_edge(0, 4)
    Gn.remove_edge(0, 4)
    Gf.add_edge(0, 1)
    Gn.add_edge(0, 1)
    assert vars(Gf)["_fnx_complete_bipartite_shape"] == original_shape
    assert Gf.edges_seq != original_shape[1]
    assert (
        fnx._complete_bipartite_normalized_laplacian_spectrum_sorted_value_safe(
            Gf, "weight"
        )
        is None
    )
    fr = fnx.normalized_laplacian_spectrum(Gf)
    nr = nx.normalized_laplacian_spectrum(Gn)
    assert fr.dtype == np.float64
    assert np.allclose(np.sort(fr), np.sort(nr))


def test_disconnected_two_regular_graph_stays_on_matrix_route():
    Gf = fnx.Graph()
    Gf.add_edges_from(
        [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4)]
    )
    Gn = nx.Graph()
    Gn.add_edges_from(
        [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4)]
    )
    fr = fnx.normalized_laplacian_spectrum(Gf)
    nr = nx.normalized_laplacian_spectrum(Gn)
    cycle = np.sort(1.0 - np.cos(2.0 * np.pi * np.arange(8, dtype=np.float64) / 8.0))
    assert fnx._cycle_normalized_laplacian_spectrum_sorted_value_safe(Gf, None) is None
    assert fr.dtype == np.float64
    assert np.allclose(np.sort(fr), np.sort(nr))
    assert not np.allclose(np.sort(fr), cycle)


_SPECTRUM_SHAPES = {
    "cycle": [(0, 1), (1, 2), (2, 3), (3, 0)],
    "path": [(0, 1), (1, 2), (2, 3)],
    "star": [(0, 1), (0, 2), (0, 3)],
    "complete": [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)],
}


def _one_bad_weight(lib, cls, shape, bad):
    graph = getattr(lib, cls)()
    for index, (u, v) in enumerate(_SPECTRUM_SHAPES[shape]):
        graph.add_edge(u, v, weight=bad if index == 1 else 1.0 + index)
    return graph


def _outcome(fn, graph):
    try:
        values = np.asarray(fn(graph), dtype=complex)
    except Exception as exc:  # noqa: BLE001 - the exception is what is compared
        return type(exc).__name__, str(exc)
    # + 0.0 folds -0.0 into 0.0, so solver sign noise on a zero eigenvalue is not a diff
    parts = zip(np.round(values.real, 6) + 0.0, np.round(values.imag, 6) + 0.0)
    return "ok", sorted((float(re), float(im)) for re, im in parts)


@pytest.mark.filterwarnings("ignore::RuntimeWarning")
@pytest.mark.parametrize("fn_name", ["laplacian_spectrum", "normalized_laplacian_spectrum"])
@pytest.mark.parametrize("cls", ["Graph", "DiGraph"])
@pytest.mark.parametrize("shape", sorted(_SPECTRUM_SHAPES))
@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -4.0], ids=["nan", "inf", "negative"])
def test_non_finite_matrix_raises_networkx_value_error(fn_name, cls, shape, bad):
    # br-r37-c1-63v34: networkx's scipy.linalg.eigvalsh rejects a nan/inf entry with
    # ValueError('array must not contain infs or NaNs'); fnx's numpy eigvalsh failed
    # later with LinAlgError. A finite negative weight must still give nx's values.
    expected = _outcome(getattr(nx, fn_name), _one_bad_weight(nx, cls, shape, bad))
    actual = _outcome(getattr(fnx, fn_name), _one_bad_weight(fnx, cls, shape, bad))
    assert actual == expected


@pytest.mark.parametrize("algorithm", ["laplacian_matrix", "normalized_laplacian_matrix"])
@pytest.mark.parametrize("kind", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph", "view"])
def test_none_key_laplacian_reads_live_weights(algorithm, kind):
    def fixture(module):
        cls = getattr(module, "Graph" if kind == "view" else kind)
        graph = module.path_graph(4, create_using=cls())
        if graph.is_multigraph():
            graph.add_edge(1, 2)
            attrs = graph[1][2][0]
        else:
            attrs = graph[1][2]
        if kind == "view":
            graph.add_edge(0, 3)
            graph = module.subgraph_view(graph, filter_edge=lambda u, v: {u, v} != {0, 3})
        return graph, attrs

    actual_graph, actual_attrs = fixture(fnx)
    reference_graph, reference_attrs = fixture(nx)
    for value in (3.0, 0.25, 2 + 1j, None):
        for attrs in (actual_attrs, reference_attrs):
            if value is None:
                del attrs[None]
            else:
                attrs[None] = value
        for order in (None, [2, 1, 0]):
            actual = getattr(fnx, algorithm)(actual_graph, weight=None, nodelist=order)
            expected = getattr(nx, algorithm)(reference_graph, weight=None, nodelist=order)
            assert actual.dtype == expected.dtype
            np.testing.assert_allclose(actual.toarray(), expected.toarray(), atol=1e-12)


@pytest.mark.parametrize("algorithm", ["laplacian_spectrum", "normalized_laplacian_spectrum"])
@pytest.mark.parametrize(
    "shape,args",
    [
        ("path_graph", (4,)), ("cycle_graph", (5,)), ("complete_graph", (5,)),
        ("star_graph", (4,)), ("complete_bipartite_graph", (2, 3)),
    ],
)
def test_none_key_laplacian_spectrum_after_weight_mutation(algorithm, shape, args):
    graphs = [getattr(module, shape)(*args) for module in (fnx, nx)]
    edge = next(iter(graphs[1].edges))
    for value in (3.0, 0.0, 2 + 1j):
        # A positive weight leaves the normalized spectrum of a star invariant.
        # A zero on a leaf edge exposes an incorrect closed-form shortcut.
        for graph in graphs:
            graph.edges[edge][None] = value
        actual = getattr(fnx, algorithm)(graphs[0], weight=None)
        expected = getattr(nx, algorithm)(graphs[1], weight=None)
        np.testing.assert_allclose(actual, expected, atol=1e-10)


@pytest.mark.parametrize("algorithm", ["laplacian_matrix", "normalized_laplacian_matrix"])
def test_none_key_laplacian_weight_added_during_nodelist_iteration(algorithm):
    def matrix(module):
        graph = module.path_graph(4)

        class NodeOrder(list):
            def __iter__(self):
                graph[1][2][None] = 3.0
                return super().__iter__()

        order = NodeOrder([3, 2, 1, 0])
        return getattr(module, algorithm)(graph, nodelist=order, weight=None).toarray()

    np.testing.assert_allclose(matrix(fnx), matrix(nx), atol=1e-12)


@pytest.mark.parametrize(
    "algorithm",
    ["laplacian_matrix", "normalized_laplacian_matrix",
     "laplacian_spectrum", "normalized_laplacian_spectrum"],
)
def test_none_key_laplacian_preserves_reentrant_key_error(algorithm):
    def outcome(module):
        graph = module.path_graph(4)
        events = []

        class CollidingKey:
            def __hash__(self):
                events.append("hash")
                return hash(None)

            def __eq__(self, other):
                if other is None:
                    events.append("compare")
                    graph.add_node(0)  # Re-enter a mutating API on the same graph.
                    raise LookupError("edge weight lookup")
                return self is other

        graph[1][2][CollidingKey()] = 3
        events.clear()
        with pytest.raises(LookupError, match="edge weight lookup"):
            getattr(module, algorithm)(graph, weight=None)
        return events

    assert outcome(fnx) == outcome(nx) == ["compare"]


@pytest.mark.parametrize("algorithm", ["laplacian_matrix", "normalized_laplacian_matrix"])
def test_none_key_laplacian_skips_excluded_edge_lookup(algorithm):
    class ExcludedKey:
        def __hash__(self):
            return hash(None)

        def __eq__(self, other):
            if other is None:
                raise AssertionError("read an edge outside the induced subgraph")
            return self is other

    def matrix(module):
        graph = module.path_graph(4)
        graph[0][1][ExcludedKey()] = 9
        graph[1][2][None] = 3
        return getattr(module, algorithm)(graph, nodelist=[1, 2, 3], weight=None).toarray()

    np.testing.assert_allclose(matrix(fnx), matrix(nx), atol=1e-12)


@pytest.mark.parametrize(
    "algorithm",
    ["laplacian_matrix", "normalized_laplacian_matrix",
     "laplacian_spectrum", "normalized_laplacian_spectrum"],
)
def test_none_key_laplacian_preserves_edge_provider_error(algorithm):
    def outcome(module):
        graph = module.complete_graph(4)
        calls = []

        def read_edges(*args, **kwargs):
            calls.append((args, kwargs))
            raise LookupError("public edge provider")

        graph.edges = read_edges
        with pytest.raises(LookupError, match="public edge provider"):
            getattr(module, algorithm)(graph, weight=None)
        return calls

    assert outcome(fnx) == outcome(nx) == [((), {"data": None, "default": 1})]


@pytest.mark.parametrize(
    "algorithm,fallback",
    [
        ("laplacian_matrix", "to_scipy_sparse_array"),
        ("normalized_laplacian_matrix", "to_scipy_sparse_array"),
        ("laplacian_spectrum", "laplacian_matrix"),
        ("normalized_laplacian_spectrum", "normalized_laplacian_matrix"),
    ],
)
def test_none_key_attribute_free_graph_keeps_shortcut(monkeypatch, algorithm, fallback):
    graph = fnx.complete_graph(5)
    expected = getattr(nx, algorithm)(nx.complete_graph(5), weight=None)

    def unexpected_fallback(*args, **kwargs):
        raise AssertionError("attribute-free graph left its unit-weight shortcut")

    monkeypatch.setattr(fnx, fallback, unexpected_fallback)
    actual = getattr(fnx, algorithm)(graph, weight=None)
    if algorithm.endswith("_matrix"):
        actual, expected = actual.toarray(), expected.toarray()
    np.testing.assert_allclose(actual, expected, atol=1e-10)


@pytest.mark.parametrize("algorithm", ["laplacian_matrix", "normalized_laplacian_matrix"])
def test_none_key_laplacian_reads_self_loop_again_for_diagonal_correction(algorithm):
    def outcome(module):
        graph = module.path_graph(4)
        graph.add_edge(2, 2)
        events = []

        class LoopKey:
            def __hash__(self):
                return hash(None)

            def __eq__(self, other):
                if other is not None:
                    return self is other
                events.append("compare")
                if len(events) == 3:
                    raise LookupError("loop correction")
                return True

        graph[2][2][LoopKey()] = 3
        with pytest.raises(LookupError, match="loop correction"):
            getattr(module, algorithm)(graph, weight=None)
        return events

    assert outcome(fnx) == outcome(nx) == ["compare"] * 3
