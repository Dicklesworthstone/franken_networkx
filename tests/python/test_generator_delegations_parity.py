import networkx as nx
import pytest

import franken_networkx as fnx

from franken_networkx.backend import _fnx_to_nx as _to_nx


def _node_key(node):
    return (type(node).__name__, repr(node))


def _edge_key(graph, edge):
    if graph.is_multigraph():
        u, v, key = edge
        ends = (_node_key(u), _node_key(v))
        if not graph.is_directed():
            ends = tuple(sorted(ends))
        return (*ends, (type(key).__name__, repr(key)))

    u, v = edge
    ends = (_node_key(u), _node_key(v))
    if not graph.is_directed():
        ends = tuple(sorted(ends))
    return ends


def _graph_signature(graph):
    nodes = list(graph.nodes())
    if graph.is_multigraph():
        edges = sorted(_edge_key(graph, edge) for edge in graph.edges(keys=True))
    else:
        edges = sorted(_edge_key(graph, edge) for edge in graph.edges())
    return (graph.is_directed(), graph.is_multigraph(), nodes, edges)


def _value_key(value):
    if isinstance(value, dict):
        return tuple(
            sorted(((type(key).__name__, repr(key)), _value_key(inner)) for key, inner in value.items())
        )
    if isinstance(value, (list, tuple)):
        return tuple(_value_key(item) for item in value)
    if isinstance(value, set):
        return tuple(sorted(_value_key(item) for item in value))
    return (type(value).__name__, repr(value))


def _mapping_key(mapping):
    return tuple(
        sorted(((type(key).__name__, repr(key)), _value_key(value)) for key, value in mapping.items())
    )


def _edge_data_key(graph, edge):
    if graph.is_multigraph():
        u, v, key, attrs = edge
        ends = (_node_key(u), _node_key(v))
        if not graph.is_directed():
            ends = tuple(sorted(ends))
        return (*ends, (type(key).__name__, repr(key)), _mapping_key(attrs))

    u, v, attrs = edge
    ends = (_node_key(u), _node_key(v))
    if not graph.is_directed():
        ends = tuple(sorted(ends))
    return (*ends, _mapping_key(attrs))


def _graph_data_signature(graph):
    nodes = [(_node_key(node), _mapping_key(attrs)) for node, attrs in graph.nodes(data=True)]
    if graph.is_multigraph():
        edges = sorted(_edge_data_key(graph, edge) for edge in graph.edges(keys=True, data=True))
    else:
        edges = sorted(_edge_data_key(graph, edge) for edge in graph.edges(data=True))
    return (
        graph.is_directed(),
        graph.is_multigraph(),
        _mapping_key(graph.graph),
        nodes,
        edges,
    )


def test_random_labeled_tree_matches_networkx_seeded_edges():
    graph = fnx.random_labeled_tree(5, seed=42)
    expected = nx.random_labeled_tree(5, seed=42)

    assert fnx.is_tree(graph)
    assert sorted(graph.edges()) == sorted(expected.edges())


def test_random_labeled_tree_rejects_null_graph():
    with pytest.raises(fnx.NetworkXPointlessConcept, match="null graph is not a tree"):
        fnx.random_labeled_tree(0, seed=42)


def test_triad_graph_matches_networkx_for_all_named_triads():
    triads = (
        "003",
        "012",
        "102",
        "021D",
        "021U",
        "021C",
        "111D",
        "111U",
        "030T",
        "030C",
        "201",
        "120D",
        "120U",
        "120C",
        "210",
        "300",
    )
    for triad_name in triads:
        graph = fnx.triad_graph(triad_name)
        expected = nx.triad_graph(triad_name)

        assert sorted(graph.nodes()) == sorted(expected.nodes())
        assert sorted(graph.edges()) == sorted(expected.edges())


def test_triad_graph_invalid_name_matches_networkx_contract():
    with pytest.raises(ValueError, match="unknown triad name"):
        fnx.triad_graph("999")


def test_random_powerlaw_tree_sequence_matches_networkx_seeded_output():
    assert fnx.random_powerlaw_tree_sequence(8, gamma=3, seed=3, tries=200) == nx.random_powerlaw_tree_sequence(
        8,
        gamma=3,
        seed=3,
        tries=200,
    )


def test_degree_sequence_tree_create_using_matches_networkx():
    expected = nx.degree_sequence_tree([1, 2, 2, 1], create_using=nx.MultiGraph())
    actual = fnx.degree_sequence_tree([1, 2, 2, 1], create_using=fnx.MultiGraph())

    assert isinstance(actual, fnx.MultiGraph)
    assert _graph_data_signature(_to_nx(actual)) == _graph_data_signature(expected)


def test_degree_sequence_tree_rejects_directed_create_using():
    with pytest.raises(fnx.NetworkXError, match="Directed Graph not supported"):
        fnx.degree_sequence_tree([1, 2, 2, 1], create_using=fnx.DiGraph())


@pytest.mark.parametrize(
    ("function_name", "args", "kwargs"),
    [
        ("configuration_model", ([2, 2, 2, 2],), {"seed": 1}),
        ("random_clustered_graph", ([(1, 0), (1, 0), (0, 1), (0, 1), (0, 1)],), {"seed": 1}),
        ("random_degree_sequence_graph", ([2, 2, 2, 2],), {"seed": 1}),
    ],
)
def test_degree_sequence_multigraph_generators_match_networkx_without_fallback(
    monkeypatch,
    function_name,
    args,
    kwargs,
):
    expected = getattr(nx, function_name)(*args, **kwargs)

    def fail(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(nx, function_name, fail)

    actual = getattr(fnx, function_name)(*args, **kwargs)

    assert _graph_data_signature(_to_nx(actual)) == _graph_data_signature(expected)


@pytest.mark.parametrize(
    ("function_name", "args", "kwargs"),
    [
        ("havel_hakimi_graph", ([3, 3, 2, 2, 2],), {"create_using": fnx.MultiGraph()}),
        ("expected_degree_graph", ([3, 3, 3, 3],), {"seed": 1, "selfloops": False}),
        ("joint_degree_graph", ({1: {1: 2}},), {"seed": 1}),
    ],
)
def test_degree_sequence_simple_generators_match_networkx_without_fallback(
    monkeypatch,
    function_name,
    args,
    kwargs,
):
    nx_kwargs = dict(kwargs)
    if "create_using" in nx_kwargs:
        nx_kwargs["create_using"] = nx.MultiGraph()
    expected = getattr(nx, function_name)(*args, **nx_kwargs)

    def fail(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(nx, function_name, fail)

    actual = getattr(fnx, function_name)(*args, **kwargs)

    assert _graph_data_signature(_to_nx(actual)) == _graph_data_signature(expected)


@pytest.mark.parametrize(
    ("function_name", "args", "kwargs"),
    [
        ("directed_configuration_model", ([1, 1], [1, 1]), {"seed": 1}),
        ("directed_havel_hakimi_graph", ([1, 1], [1, 1]), {}),
        (
            "directed_joint_degree_graph",
            ([0, 1, 1, 2], [1, 1, 1, 1], {1: {1: 2, 2: 2}}),
            {"seed": 1},
        ),
    ],
)
def test_directed_degree_sequence_generators_match_networkx_without_fallback(
    monkeypatch,
    function_name,
    args,
    kwargs,
):
    expected = getattr(nx, function_name)(*args, **kwargs)

    def fail(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(nx, function_name, fail)

    actual = getattr(fnx, function_name)(*args, **kwargs)

    assert _graph_data_signature(_to_nx(actual)) == _graph_data_signature(expected)


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda: fnx.configuration_model([1, 2]), "sum of degrees must be even"),
        (lambda: fnx.havel_hakimi_graph([4, 1, 1]), "Invalid degree sequence"),
        (
            lambda: fnx.directed_configuration_model([1], [2]),
            "sequences must have equal sums",
        ),
        (
            lambda: fnx.directed_havel_hakimi_graph([1], [2]),
            "Sequences must have equal sums",
        ),
        (
            lambda: fnx.random_clustered_graph([(1, 1), (2, 1), (0, 1)]),
            "Invalid degree sequence",
        ),
        (
            lambda: fnx.random_degree_sequence_graph([3, 1, 1]),
            "degree sequence is not graphical",
        ),
    ],
)
def test_degree_sequence_generators_preserve_error_contracts(call, message):
    with pytest.raises((fnx.NetworkXError, fnx.NetworkXUnfeasible), match=message):
        call()


@pytest.mark.parametrize(
    ("function_name", "args", "kwargs", "nx_factory", "fnx_factory"),
    [
        ("gn_graph", (8,), {"seed": 42}, nx.DiGraph, fnx.DiGraph),
        ("gn_graph", (8,), {"seed": 42}, nx.MultiDiGraph, fnx.MultiDiGraph),
        ("gnr_graph", (8, 0.4), {"seed": 42}, nx.DiGraph, fnx.DiGraph),
        ("gnr_graph", (8, 0.4), {"seed": 42}, nx.MultiDiGraph, fnx.MultiDiGraph),
        ("gnc_graph", (8,), {"seed": 42}, nx.DiGraph, fnx.DiGraph),
        ("gnc_graph", (8,), {"seed": 42}, nx.MultiDiGraph, fnx.MultiDiGraph),
    ],
)
def test_directed_growth_generator_create_using_matches_networkx_without_fallback(
    monkeypatch,
    function_name,
    args,
    kwargs,
    nx_factory,
    fnx_factory,
):
    expected = getattr(nx, function_name)(*args, create_using=nx_factory(), **kwargs)

    def fail(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(nx, function_name, fail)

    actual = getattr(fnx, function_name)(*args, create_using=fnx_factory(), **kwargs)

    assert isinstance(actual, fnx_factory)
    assert _graph_data_signature(_to_nx(actual)) == _graph_data_signature(expected)


@pytest.mark.parametrize(
    ("function_name", "args", "kwargs"),
    [
        ("gn_graph", (8,), {"seed": 42}),
        ("gnr_graph", (8, 0.4), {"seed": 42}),
        ("gnc_graph", (8,), {"seed": 42}),
    ],
)
def test_directed_growth_generator_rejects_undirected_create_using_without_fallback(
    monkeypatch,
    function_name,
    args,
    kwargs,
):
    def fail(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(nx, function_name, fail)

    with pytest.raises(fnx.NetworkXError, match="create_using must indicate a Directed Graph"):
        getattr(fnx, function_name)(*args, create_using=fnx.Graph(), **kwargs)


def test_gn_graph_kernel_matches_networkx_without_fallback(monkeypatch):
    expected = nx.gn_graph(
        8,
        kernel=lambda degree: degree**1.5,
        seed=42,
        create_using=nx.MultiDiGraph(),
    )

    def fail(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(nx, "gn_graph", fail)

    actual = fnx.gn_graph(
        8,
        kernel=lambda degree: degree**1.5,
        seed=42,
        create_using=fnx.MultiDiGraph(),
    )

    assert isinstance(actual, fnx.MultiDiGraph)
    assert _graph_data_signature(_to_nx(actual)) == _graph_data_signature(expected)


@pytest.mark.parametrize(
    ("function_name", "args", "kwargs", "nx_factory", "fnx_factory"),
    [
        ("gnp_random_graph", (8, 0.2), {"seed": 42}, nx.Graph, fnx.Graph),
        ("gnp_random_graph", (8, 0.2), {"seed": 42, "directed": True}, nx.DiGraph, fnx.DiGraph),
        ("fast_gnp_random_graph", (8, 0.2), {"seed": 42}, nx.Graph, fnx.Graph),
        ("fast_gnp_random_graph", (8, 0.2), {"seed": 42, "directed": True}, nx.DiGraph, fnx.DiGraph),
        ("dense_gnm_random_graph", (8, 7), {"seed": 42}, nx.Graph, fnx.Graph),
        ("random_regular_graph", (2, 8), {"seed": 42}, nx.Graph, fnx.Graph),
        ("random_powerlaw_tree", (8,), {"gamma": 3, "seed": 3, "tries": 200}, nx.Graph, fnx.Graph),
    ],
)
def test_random_wrapper_create_using_matches_networkx_without_fallback(
    monkeypatch,
    function_name,
    args,
    kwargs,
    nx_factory,
    fnx_factory,
):
    expected = getattr(nx, function_name)(*args, create_using=nx_factory(), **kwargs)

    def fail(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(nx, function_name, fail)

    actual = getattr(fnx, function_name)(*args, create_using=fnx_factory(), **kwargs)

    assert isinstance(actual, fnx_factory)
    assert _graph_data_signature(_to_nx(actual)) == _graph_data_signature(expected)


def test_erdos_renyi_graph_create_using_matches_networkx_without_fallback(monkeypatch):
    expected = nx.erdos_renyi_graph(8, 0.2, seed=42, directed=True, create_using=nx.DiGraph())

    def fail(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(nx, "erdos_renyi_graph", fail)
    monkeypatch.setattr(nx, "gnp_random_graph", fail)

    actual = fnx.erdos_renyi_graph(8, 0.2, seed=42, directed=True, create_using=fnx.DiGraph())

    assert isinstance(actual, fnx.DiGraph)
    assert _graph_data_signature(_to_nx(actual)) == _graph_data_signature(expected)


def test_binomial_graph_create_using_matches_networkx_without_fallback(monkeypatch):
    expected = nx.binomial_graph(8, 0.2, seed=42, create_using=nx.Graph())

    def fail(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(nx, "binomial_graph", fail)
    monkeypatch.setattr(nx, "gnp_random_graph", fail)

    actual = fnx.binomial_graph(8, 0.2, seed=42, create_using=fnx.Graph())

    assert isinstance(actual, fnx.Graph)
    assert _graph_data_signature(_to_nx(actual)) == _graph_data_signature(expected)


@pytest.mark.parametrize(
    ("function_name", "args", "kwargs", "graph_factory", "message"),
    [
        ("gnp_random_graph", (8, 0.2), {"seed": 42}, fnx.DiGraph, "create_using must not be directed"),
        ("gnp_random_graph", (8, 0.2), {"seed": 42}, fnx.MultiGraph, "create_using must not be a multi-graph"),
        ("gnp_random_graph", (8, 0.2), {"seed": 42, "directed": True}, fnx.Graph, "create_using must be directed"),
        ("gnp_random_graph", (8, 0.2), {"seed": 42, "directed": True}, fnx.MultiDiGraph, "create_using must not be a multi-graph"),
        ("fast_gnp_random_graph", (8, 0.2), {"seed": 42, "directed": True}, fnx.Graph, "create_using must be directed"),
        ("dense_gnm_random_graph", (8, 7), {"seed": 42}, fnx.MultiGraph, "create_using must not be a multi-graph"),
        ("random_regular_graph", (2, 8), {"seed": 42}, fnx.DiGraph, "create_using must not be directed"),
        ("random_powerlaw_tree", (8,), {"gamma": 3, "seed": 3, "tries": 200}, fnx.DiGraph, "create_using must not be directed"),
    ],
)
def test_random_wrapper_invalid_create_using_matches_networkx_without_fallback(
    monkeypatch,
    function_name,
    args,
    kwargs,
    graph_factory,
    message,
):
    def fail(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(nx, function_name, fail)
    if function_name in {"gnp_random_graph", "erdos_renyi_graph", "binomial_graph"}:
        monkeypatch.setattr(nx, "gnp_random_graph", fail)

    with pytest.raises(fnx.NetworkXError, match=message):
        getattr(fnx, function_name)(*args, create_using=graph_factory(), **kwargs)


def test_empty_graph_iterable_default_matches_networkx_without_fallback(monkeypatch):
    expected = nx.empty_graph("abc", default=nx.DiGraph)

    def fail(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(nx, "empty_graph", fail)

    actual = fnx.empty_graph("abc", default=fnx.DiGraph)

    assert isinstance(actual, fnx.DiGraph)
    assert _graph_signature(_to_nx(actual)) == _graph_signature(expected)


def test_empty_graph_invalid_create_using_matches_networkx_contract():
    with pytest.raises(TypeError, match="create_using is not a valid NetworkX graph type or instance"):
        fnx.empty_graph(create_using=0.0)


def test_complete_graph_iterable_multigraph_matches_networkx_without_fallback(monkeypatch):
    expected = nx.complete_graph("abcb", create_using=nx.MultiGraph())

    def fail(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(nx, "complete_graph", fail)

    actual = fnx.complete_graph("abcb", create_using=fnx.MultiGraph())

    assert isinstance(actual, fnx.MultiGraph)
    assert _graph_signature(_to_nx(actual)) == _graph_signature(expected)


def test_cycle_graph_iterable_digraph_matches_networkx_without_fallback(monkeypatch):
    expected = nx.cycle_graph("abcb", create_using=nx.DiGraph())

    def fail(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(nx, "cycle_graph", fail)

    actual = fnx.cycle_graph("abcb", create_using=fnx.DiGraph())

    assert isinstance(actual, fnx.DiGraph)
    assert _graph_signature(_to_nx(actual)) == _graph_signature(expected)


def test_path_graph_iterable_digraph_matches_networkx_without_fallback(monkeypatch):
    expected = nx.path_graph((1, 2, 3, 2, 4), create_using=nx.DiGraph())

    def fail(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(nx, "path_graph", fail)

    actual = fnx.path_graph((1, 2, 3, 2, 4), create_using=fnx.DiGraph())

    assert isinstance(actual, fnx.DiGraph)
    assert _graph_signature(_to_nx(actual)) == _graph_signature(expected)


def test_star_graph_iterable_multigraph_matches_networkx_without_fallback(monkeypatch):
    expected = nx.star_graph("abcb", create_using=nx.MultiGraph())

    def fail(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(nx, "star_graph", fail)

    actual = fnx.star_graph("abcb", create_using=fnx.MultiGraph())

    assert isinstance(actual, fnx.MultiGraph)
    assert _graph_signature(_to_nx(actual)) == _graph_signature(expected)


def test_null_and_trivial_graph_create_using_match_networkx_without_fallback(monkeypatch):
    expected_null = nx.null_graph(create_using=nx.MultiGraph())
    expected_trivial = nx.trivial_graph(create_using=nx.DiGraph())

    def fail(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(nx, "null_graph", fail)
    monkeypatch.setattr(nx, "trivial_graph", fail)

    actual_null = fnx.null_graph(create_using=fnx.MultiGraph())
    actual_trivial = fnx.trivial_graph(create_using=fnx.DiGraph())

    assert isinstance(actual_null, fnx.MultiGraph)
    assert isinstance(actual_trivial, fnx.DiGraph)
    assert _graph_signature(_to_nx(actual_null)) == _graph_signature(expected_null)
    assert _graph_signature(_to_nx(actual_trivial)) == _graph_signature(expected_trivial)


@pytest.mark.parametrize(
    ("function_name", "args", "kwargs", "nx_factory", "fnx_factory"),
    [
        ("balanced_tree", (2, 2), {}, nx.DiGraph, fnx.DiGraph),
        ("full_rary_tree", (2, 7), {}, nx.MultiDiGraph, fnx.MultiDiGraph),
        ("binomial_tree", (3,), {}, nx.DiGraph, fnx.DiGraph),
        ("complete_bipartite_graph", (("a", "b"), ("x", "y")), {}, nx.MultiGraph, fnx.MultiGraph),
        ("grid_2d_graph", (2, 3), {"periodic": (True, False)}, nx.DiGraph, fnx.DiGraph),
        ("barbell_graph", (3, 1), {}, nx.MultiGraph, fnx.MultiGraph),
        ("circular_ladder_graph", (4,), {}, nx.MultiGraph, fnx.MultiGraph),
        ("ladder_graph", (4,), {}, nx.MultiGraph, fnx.MultiGraph),
        ("lollipop_graph", (["a", "b", "c"], ["d", "e"]), {}, nx.MultiGraph, fnx.MultiGraph),
        ("tadpole_graph", (["a", "b", "c"], ["d", "e"]), {}, nx.MultiGraph, fnx.MultiGraph),
        ("wheel_graph", (["hub", "a", "b", "c"],), {}, nx.MultiGraph, fnx.MultiGraph),
        ("circulant_graph", (6, [1, 2]), {}, nx.MultiDiGraph, fnx.MultiDiGraph),
        ("generalized_petersen_graph", (5, 2), {}, nx.MultiGraph, fnx.MultiGraph),
    ],
)
def test_classic_generator_create_using_matches_networkx_without_fallback(
    monkeypatch,
    function_name,
    args,
    kwargs,
    nx_factory,
    fnx_factory,
):
    expected = getattr(nx, function_name)(*args, create_using=nx_factory(), **kwargs)

    def fail(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(nx, function_name, fail)

    actual = getattr(fnx, function_name)(*args, create_using=fnx_factory(), **kwargs)

    assert isinstance(actual, fnx_factory)
    assert _graph_data_signature(_to_nx(actual)) == _graph_data_signature(expected)


@pytest.mark.parametrize(
    ("function_name", "args", "kwargs", "message"),
    [
        ("complete_bipartite_graph", (3, 4), {}, "Directed Graph not supported"),
        ("barbell_graph", (3, 1), {}, "Directed Graph not supported"),
        ("circular_ladder_graph", (4,), {}, "Directed Graph not supported"),
        ("ladder_graph", (4,), {}, "Directed Graph not supported"),
        ("lollipop_graph", (["a", "b", "c"], ["d", "e"]), {}, "Directed Graph not supported"),
        ("tadpole_graph", (["a", "b", "c"], ["d", "e"]), {}, "Directed Graph not supported"),
        ("wheel_graph", (["hub", "a", "b", "c"],), {}, "Directed Graph not supported"),
        ("generalized_petersen_graph", (5, 2), {}, "Directed Graph not supported in create_using"),
    ],
)
def test_classic_generator_rejects_directed_create_using_without_fallback(
    monkeypatch,
    function_name,
    args,
    kwargs,
    message,
):
    def fail(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(nx, function_name, fail)

    with pytest.raises(fnx.NetworkXError, match=message):
        getattr(fnx, function_name)(*args, create_using=fnx.DiGraph(), **kwargs)


@pytest.mark.parametrize(
    ("function_name", "args", "kwargs", "nx_factory", "fnx_factory"),
    [
        ("bull_graph", (), {}, nx.MultiGraph, fnx.MultiGraph),
        ("diamond_graph", (), {}, nx.MultiGraph, fnx.MultiGraph),
        ("house_graph", (), {}, nx.MultiGraph, fnx.MultiGraph),
        ("house_x_graph", (), {}, nx.MultiGraph, fnx.MultiGraph),
        ("cubical_graph", (), {}, nx.MultiGraph, fnx.MultiGraph),
        ("petersen_graph", (), {}, nx.MultiGraph, fnx.MultiGraph),
        ("tetrahedral_graph", (), {}, nx.DiGraph, fnx.DiGraph),
        ("desargues_graph", (), {}, nx.MultiGraph, fnx.MultiGraph),
        ("dodecahedral_graph", (), {}, nx.MultiGraph, fnx.MultiGraph),
        ("heawood_graph", (), {}, nx.MultiGraph, fnx.MultiGraph),
        ("moebius_kantor_graph", (), {}, nx.MultiGraph, fnx.MultiGraph),
        ("octahedral_graph", (), {}, nx.MultiGraph, fnx.MultiGraph),
        ("truncated_cube_graph", (), {}, nx.MultiGraph, fnx.MultiGraph),
        ("truncated_tetrahedron_graph", (), {}, nx.DiGraph, fnx.DiGraph),
        ("chvatal_graph", (), {}, nx.MultiGraph, fnx.MultiGraph),
        ("frucht_graph", (), {}, nx.DiGraph, fnx.DiGraph),
        ("icosahedral_graph", (), {}, nx.MultiGraph, fnx.MultiGraph),
        ("krackhardt_kite_graph", (), {}, nx.MultiGraph, fnx.MultiGraph),
        ("tutte_graph", (), {}, nx.MultiGraph, fnx.MultiGraph),
        ("paley_graph", (5,), {}, nx.DiGraph, fnx.DiGraph),
        ("chordal_cycle_graph", (5,), {}, nx.MultiGraph, fnx.MultiGraph),
    ],
)
def test_named_classic_generator_create_using_matches_networkx_without_fallback(
    monkeypatch,
    function_name,
    args,
    kwargs,
    nx_factory,
    fnx_factory,
):
    expected = getattr(nx, function_name)(*args, create_using=nx_factory(), **kwargs)

    def fail(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(nx, function_name, fail)

    actual = getattr(fnx, function_name)(*args, create_using=fnx_factory(), **kwargs)

    assert isinstance(actual, fnx_factory)
    assert _graph_data_signature(_to_nx(actual)) == _graph_data_signature(expected)


@pytest.mark.parametrize(
    ("function_name", "message"),
    [
        ("bull_graph", "Directed Graph not supported in create_using"),
        ("diamond_graph", "Directed Graph not supported in create_using"),
        ("house_graph", "Directed Graph not supported in create_using"),
        ("house_x_graph", "Directed Graph not supported in create_using"),
        ("cubical_graph", "Directed Graph not supported in create_using"),
        ("petersen_graph", "Directed Graph not supported in create_using"),
        ("desargues_graph", "Directed Graph not supported"),
        ("dodecahedral_graph", "Directed Graph not supported"),
        ("heawood_graph", "Directed Graph not supported"),
        ("moebius_kantor_graph", "Directed Graph not supported"),
        ("octahedral_graph", "Directed Graph not supported in create_using"),
        ("truncated_cube_graph", "Directed Graph not supported in create_using"),
        ("chvatal_graph", "Directed Graph not supported in create_using"),
        ("icosahedral_graph", "Directed Graph not supported in create_using"),
        ("krackhardt_kite_graph", "Directed Graph not supported in create_using"),
        ("tutte_graph", "Directed Graph not supported in create_using"),
    ],
)
def test_named_classic_generator_rejects_directed_create_using_without_fallback(
    monkeypatch, function_name, message
):
    def fail(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(nx, function_name, fail)

    with pytest.raises(fnx.NetworkXError, match=message):
        getattr(fnx, function_name)(create_using=fnx.DiGraph())


def test_lcf_graph_create_using_matches_networkx_without_fallback(monkeypatch):
    expected = nx.LCF_graph(14, [5, -5], 7, create_using=nx.MultiGraph())

    def fail(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(nx, "LCF_graph", fail)

    actual = fnx.LCF_graph(14, [5, -5], 7, create_using=fnx.MultiGraph())

    assert isinstance(actual, fnx.MultiGraph)
    assert _graph_data_signature(_to_nx(actual)) == _graph_data_signature(expected)


def test_lcf_graph_rejects_directed_create_using_without_fallback(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(nx, "LCF_graph", fail)

    with pytest.raises(fnx.NetworkXError, match="Directed Graph not supported"):
        fnx.LCF_graph(14, [5, -5], 7, create_using=fnx.DiGraph())


def test_paley_graph_rejects_multigraph_create_using_without_fallback(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(nx, "paley_graph", fail)

    with pytest.raises(fnx.NetworkXError, match="`create_using` cannot be a multigraph."):
        fnx.paley_graph(5, create_using=fnx.MultiGraph())


def test_chordal_cycle_graph_requires_undirected_multigraph_without_fallback(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(nx, "chordal_cycle_graph", fail)

    with pytest.raises(
        fnx.NetworkXError, match="`create_using` must be an undirected multigraph."
    ):
        fnx.chordal_cycle_graph(5, create_using=fnx.Graph())


def test_barabasi_albert_with_initial_graph_matches_networkx_without_fallback(monkeypatch):
    initial = fnx.path_graph(3)
    expected_initial = nx.path_graph(3)
    real_barabasi_albert_graph = nx.barabasi_albert_graph

    def fail(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(nx, "barabasi_albert_graph", fail)

    graph = fnx.barabasi_albert_graph(6, 1, seed=42, initial_graph=initial)
    expected = real_barabasi_albert_graph(6, 1, seed=42, initial_graph=expected_initial)

    assert sorted(graph.edges()) == sorted(expected.edges())


def test_random_unlabeled_rooted_forest_matches_networkx_roots_and_edges():
    graph = fnx.random_unlabeled_rooted_forest(3, q=2, seed=1)
    expected = nx.random_unlabeled_rooted_forest(3, q=2, seed=1)

    assert sorted(_to_nx(graph).edges()) == sorted(expected.edges())
    assert graph.graph["roots"] == expected.graph["roots"]


def test_random_unlabeled_rooted_forest_uses_local_sampler_without_networkx_fallback(monkeypatch):
    expected = nx.random_unlabeled_rooted_forest(3, q=2, seed=1)

    def fail(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(nx, "random_unlabeled_rooted_forest", fail)

    graph = fnx.random_unlabeled_rooted_forest(3, q=2, seed=1)

    assert sorted(_to_nx(graph).edges()) == sorted(expected.edges())
    assert graph.graph["roots"] == expected.graph["roots"]


def test_random_unlabeled_rooted_forest_supports_number_of_forests():
    forests = fnx.random_unlabeled_rooted_forest(3, q=2, number_of_forests=2, seed=1)

    assert len(forests) == 2
    assert all(isinstance(graph, fnx.Graph) for graph in forests)


def test_random_unlabeled_rooted_forest_matches_networkx_with_random_instance_seed():
    import random

    fnx_forests = fnx.random_unlabeled_rooted_forest(
        6,
        q=3,
        number_of_forests=3,
        seed=random.Random(7),
    )
    expected_forests = nx.random_unlabeled_rooted_forest(
        6,
        q=3,
        number_of_forests=3,
        seed=random.Random(7),
    )

    assert [
        (sorted(_to_nx(graph).edges()), graph.graph["roots"]) for graph in fnx_forests
    ] == [(sorted(graph.edges()), graph.graph["roots"]) for graph in expected_forests]


def test_random_unlabeled_rooted_tree_matches_networkx_root_and_edges():
    graph = fnx.random_unlabeled_rooted_tree(5, seed=42)
    expected = nx.random_unlabeled_rooted_tree(5, seed=42)

    assert sorted(_to_nx(graph).edges()) == sorted(expected.edges())
    assert graph.graph["root"] == expected.graph["root"]


def test_random_unlabeled_rooted_tree_supports_number_of_trees():
    trees = fnx.random_unlabeled_rooted_tree(4, number_of_trees=2, seed=3)

    assert len(trees) == 2
    assert all(isinstance(graph, fnx.Graph) for graph in trees)
    assert all(graph.graph["root"] == 0 for graph in trees)


def test_random_unlabeled_rooted_tree_rejects_null_graph():
    with pytest.raises(fnx.NetworkXPointlessConcept, match="null graph is not a tree"):
        fnx.random_unlabeled_rooted_tree(0, seed=1234)


def test_random_unlabeled_rooted_tree_matches_networkx_with_random_instance_seed():
    import random

    fnx_trees = fnx.random_unlabeled_rooted_tree(6, number_of_trees=3, seed=random.Random(7))
    expected_trees = nx.random_unlabeled_rooted_tree(6, number_of_trees=3, seed=random.Random(7))

    assert [(sorted(_to_nx(graph).edges()), graph.graph["root"]) for graph in fnx_trees] == [
        (sorted(graph.edges()), graph.graph["root"]) for graph in expected_trees
    ]


def test_random_unlabeled_rooted_tree_supports_numpy_seed_adapter():
    numpy = pytest.importorskip("numpy")

    fnx_tree = fnx.random_unlabeled_rooted_tree(5, seed=numpy.random.default_rng(9))
    expected_tree = nx.random_unlabeled_rooted_tree(5, seed=numpy.random.default_rng(9))

    assert sorted(_to_nx(fnx_tree).edges()) == sorted(expected_tree.edges())
    assert fnx_tree.graph["root"] == expected_tree.graph["root"]
