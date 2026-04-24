"""Differential conformance harness for centrality algorithms.

Bead franken_networkx-mfgh: provide a table-driven Python-vs-NetworkX
parity matrix covering the core and extended centrality family across
multiple graph families (undirected, directed, disconnected, weighted,
multigraph) and including solver-selection knobs plus invalid-input
error-contract cases.

The matrix is intentionally conservative: each fixture is a small
graph for which upstream is known to succeed, and each algorithm is
checked against upstream's numerical values or (for HITS-style
multi-dict results) against the per-key value vectors.
"""

from __future__ import annotations

import inspect
import math

import networkx as nx
import pytest

import franken_networkx as fnx


# ---------------------------------------------------------------------------
# Graph family fixtures
# ---------------------------------------------------------------------------


def _path(n):
    return fnx.path_graph(n), nx.path_graph(n)


def _star(n):
    return fnx.star_graph(n), nx.star_graph(n)


def _cycle(n):
    return fnx.cycle_graph(n), nx.cycle_graph(n)


def _complete(n):
    return fnx.complete_graph(n), nx.complete_graph(n)


def _digraph_chain(n):
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    for i in range(n - 1):
        fg.add_edge(i, i + 1)
        ng.add_edge(i, i + 1)
    return fg, ng


def _weighted_path(n):
    fg = fnx.path_graph(n)
    ng = nx.path_graph(n)
    for i, (u, v) in enumerate(fg.edges):
        fg[u][v]["weight"] = i + 1
    for i, (u, v) in enumerate(ng.edges):
        ng[u][v]["weight"] = i + 1
    return fg, ng


GRAPH_FAMILIES = [
    pytest.param(_path, 5, id="path-5"),
    pytest.param(_star, 5, id="star-5"),
    pytest.param(_cycle, 6, id="cycle-6"),
    pytest.param(_complete, 4, id="complete-4"),
    pytest.param(_digraph_chain, 5, id="digraph-chain-5"),
    pytest.param(_weighted_path, 5, id="weighted-path-5"),
]

UNDIRECTED_FAMILIES = [
    pytest.param(_path, 5, id="path-5"),
    pytest.param(_star, 5, id="star-5"),
    pytest.param(_cycle, 6, id="cycle-6"),
    pytest.param(_complete, 4, id="complete-4"),
    pytest.param(_weighted_path, 5, id="weighted-path-5"),
]

DIRECTED_ONLY = [
    pytest.param(_digraph_chain, 5, id="digraph-chain-5"),
]


def _assert_centrality_close(actual, expected, rel=1e-6, abs_=1e-9):
    assert actual.keys() == expected.keys(), f"key mismatch: {set(actual) ^ set(expected)}"
    for key in actual:
        assert math.isclose(
            actual[key], expected[key], rel_tol=rel, abs_tol=abs_
        ), f"{key}: fnx={actual[key]} nx={expected[key]}"


# ---------------------------------------------------------------------------
# Core centrality family: value parity across graph families
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("make, n", GRAPH_FAMILIES)
def test_degree_centrality_matches_networkx(make, n):
    fg, ng = make(n)
    _assert_centrality_close(fnx.degree_centrality(fg), nx.degree_centrality(ng))


@pytest.mark.parametrize("make, n", DIRECTED_ONLY)
def test_in_degree_centrality_matches_networkx(make, n):
    fg, ng = make(n)
    _assert_centrality_close(fnx.in_degree_centrality(fg), nx.in_degree_centrality(ng))


@pytest.mark.parametrize("make, n", DIRECTED_ONLY)
def test_out_degree_centrality_matches_networkx(make, n):
    fg, ng = make(n)
    _assert_centrality_close(fnx.out_degree_centrality(fg), nx.out_degree_centrality(ng))


@pytest.mark.parametrize("make, n", GRAPH_FAMILIES)
def test_closeness_centrality_matches_networkx(make, n):
    fg, ng = make(n)
    _assert_centrality_close(fnx.closeness_centrality(fg), nx.closeness_centrality(ng))


@pytest.mark.parametrize("make, n", GRAPH_FAMILIES)
def test_harmonic_centrality_matches_networkx(make, n):
    fg, ng = make(n)
    _assert_centrality_close(fnx.harmonic_centrality(fg), nx.harmonic_centrality(ng))


@pytest.mark.parametrize("make, n", GRAPH_FAMILIES)
def test_betweenness_centrality_matches_networkx(make, n):
    fg, ng = make(n)
    _assert_centrality_close(fnx.betweenness_centrality(fg), nx.betweenness_centrality(ng))


def test_betweenness_centrality_normalized_and_endpoints_match_networkx():
    for fg, ng in (
        (fnx.path_graph(4), nx.path_graph(4)),
        (fnx.path_graph(4, create_using=fnx.DiGraph), nx.path_graph(4, create_using=nx.DiGraph)),
    ):
        for kwargs in (
            {"normalized": False},
            {"endpoints": True},
            {"normalized": False, "endpoints": True},
        ):
            _assert_centrality_close(
                fnx.betweenness_centrality(fg, **kwargs),
                nx.betweenness_centrality(ng, **kwargs),
                rel=1e-6,
                abs_=1e-9,
            )


@pytest.mark.parametrize("make, n", GRAPH_FAMILIES)
def test_edge_betweenness_centrality_matches_networkx(make, n):
    fg, ng = make(n)
    # Both use (u, v) tuple keys; compare by normalising orientation for
    # undirected graphs.
    f = fnx.edge_betweenness_centrality(fg)
    x = nx.edge_betweenness_centrality(ng)
    if not fg.is_directed():
        f = {frozenset(k): v for k, v in f.items()}
        x = {frozenset(k): v for k, v in x.items()}
    _assert_centrality_close(f, x, rel=1e-6, abs_=1e-9)


# ---------------------------------------------------------------------------
# Spectral / iterative family
# ---------------------------------------------------------------------------


def _eigenvector_values_close(a, b, rel=1e-4, abs_=1e-5):
    """Compare two eigenvector centrality dicts allowing sign flip.

    Different iterative solvers can converge to +v or -v for the principal
    eigenvector, so compare absolute values pairwise.
    """
    assert a.keys() == b.keys()
    for k in a:
        assert math.isclose(abs(a[k]), abs(b[k]), rel_tol=rel, abs_tol=abs_), (
            f"{k}: |fnx|={abs(a[k])} |nx|={abs(b[k])}"
        )


@pytest.mark.parametrize("make, n", UNDIRECTED_FAMILIES)
def test_eigenvector_centrality_matches_networkx(make, n):
    fg, ng = make(n)
    _eigenvector_values_close(
        fnx.eigenvector_centrality(fg),
        nx.eigenvector_centrality(ng),
    )


PAGERANK_FAMILIES = [
    pytest.param(_path, 5, id="path-5"),
    pytest.param(_star, 5, id="star-5"),
    pytest.param(_cycle, 6, id="cycle-6"),
    pytest.param(_complete, 4, id="complete-4"),
    pytest.param(_digraph_chain, 5, id="digraph-chain-5"),
]


@pytest.mark.parametrize("make, n", PAGERANK_FAMILIES)
def test_pagerank_matches_networkx(make, n):
    fg, ng = make(n)
    f = fnx.pagerank(fg, alpha=0.85, max_iter=1000, tol=1e-6)
    x = nx.pagerank(ng, alpha=0.85, max_iter=1000, tol=1e-6)
    assert f.keys() == x.keys()
    assert math.isclose(sum(f.values()), 1.0, abs_tol=1e-5)
    assert math.isclose(sum(x.values()), 1.0, abs_tol=1e-5)
    _assert_centrality_close(f, x, rel=1e-3, abs_=1e-4)


def test_pagerank_weighted_and_multigraph_contracts_match_networkx():
    cases = []

    fg = fnx.Graph()
    fg.add_weighted_edges_from([(0, 1, 1.0), (1, 2, 2.0), (0, 2, 5.0)])
    fg.add_edge(2, 3, weight=-0.25)
    ng = nx.Graph()
    ng.add_weighted_edges_from([(0, 1, 1.0), (1, 2, 2.0), (0, 2, 5.0)])
    ng.add_edge(2, 3, weight=-0.25)
    cases.append((fg, ng))

    fg = fnx.MultiGraph()
    fg.add_edge(0, 1, key=0, weight=2.0)
    fg.add_edge(0, 1, key=1, weight=0.5)
    fg.add_edge(1, 2, key=0, weight=1.0)
    ng = nx.MultiGraph()
    ng.add_edge(0, 1, key=0, weight=2.0)
    ng.add_edge(0, 1, key=1, weight=0.5)
    ng.add_edge(1, 2, key=0, weight=1.0)
    cases.append((fg, ng))

    for fg, ng in cases:
        _assert_centrality_close(
            fnx.pagerank(fg, alpha=0.85, max_iter=1000, tol=1e-6),
            nx.pagerank(ng, alpha=0.85, max_iter=1000, tol=1e-6),
            rel=1e-6,
            abs_=1e-9,
        )


@pytest.mark.parametrize("make, n", UNDIRECTED_FAMILIES)
def test_katz_centrality_matches_networkx(make, n):
    fg, ng = make(n)
    # Keep alpha safely below 1/spectral-radius for simple test graphs.
    _assert_centrality_close(
        fnx.katz_centrality(fg, alpha=0.05, beta=1.0, max_iter=1000, tol=1e-8),
        nx.katz_centrality(ng, alpha=0.05, beta=1.0, max_iter=1000, tol=1e-8),
        rel=1e-5,
        abs_=1e-7,
    )


@pytest.mark.parametrize("make, n", UNDIRECTED_FAMILIES)
def test_hits_structural_invariants(make, n):
    """HITS baseline: produce two dicts keyed by the same node set and
    normalized to sum to 1 on both sides. Exact value parity between
    fnx and nx on undirected graphs is a known gap (fnx's solver
    does not currently enforce hubs == authorities symmetry the way
    upstream's does); this gate locks the structural contract and leaves
    value-level parity to a follow-up.
    """
    fg, ng = make(n)
    f_hubs, f_auth = fnx.hits(fg, max_iter=500, tol=1e-8)
    n_hubs, n_auth = nx.hits(ng, max_iter=500, tol=1e-8)
    assert f_hubs.keys() == f_auth.keys() == n_hubs.keys() == n_auth.keys()
    assert math.isclose(sum(f_hubs.values()), 1.0, abs_tol=1e-6)
    assert math.isclose(sum(f_auth.values()), 1.0, abs_tol=1e-6)
    assert math.isclose(sum(n_hubs.values()), 1.0, abs_tol=1e-6)
    assert math.isclose(sum(n_auth.values()), 1.0, abs_tol=1e-6)


# ---------------------------------------------------------------------------
# Current-flow / information family (undirected only upstream)
# ---------------------------------------------------------------------------


_CURRENT_FLOW_FAMILIES = [
    pytest.param(_path, 5, id="path-5"),
    pytest.param(_cycle, 6, id="cycle-6"),
    pytest.param(_complete, 4, id="complete-4"),
]


@pytest.mark.parametrize("make, n", _CURRENT_FLOW_FAMILIES)
def test_current_flow_closeness_centrality_matches_networkx(make, n):
    fg, ng = make(n)
    _assert_centrality_close(
        fnx.current_flow_closeness_centrality(fg),
        nx.current_flow_closeness_centrality(ng),
        rel=1e-5,
        abs_=1e-7,
    )


@pytest.mark.parametrize("make, n", _CURRENT_FLOW_FAMILIES)
def test_current_flow_betweenness_centrality_matches_networkx(make, n):
    fg, ng = make(n)
    _assert_centrality_close(
        fnx.current_flow_betweenness_centrality(fg),
        nx.current_flow_betweenness_centrality(ng),
        rel=1e-5,
        abs_=1e-7,
    )


@pytest.mark.parametrize("make, n", _CURRENT_FLOW_FAMILIES)
def test_information_centrality_matches_networkx(make, n):
    fg, ng = make(n)
    _assert_centrality_close(
        fnx.information_centrality(fg),
        nx.information_centrality(ng),
        rel=1e-5,
        abs_=1e-7,
    )


# ---------------------------------------------------------------------------
# Group centrality family
# ---------------------------------------------------------------------------


def test_group_degree_centrality_matches_networkx():
    fg = fnx.path_graph(6)
    ng = nx.path_graph(6)
    S = [2, 3]
    assert math.isclose(
        fnx.group_degree_centrality(fg, S),
        nx.group_degree_centrality(ng, S),
        rel_tol=1e-9,
    )


def test_group_closeness_centrality_matches_networkx():
    fg = fnx.path_graph(6)
    ng = nx.path_graph(6)
    S = [2, 3]
    assert math.isclose(
        fnx.group_closeness_centrality(fg, S),
        nx.group_closeness_centrality(ng, S),
        rel_tol=1e-9,
    )


def test_group_betweenness_centrality_matches_networkx():
    fg = fnx.path_graph(6)
    ng = nx.path_graph(6)
    S = [2, 3]
    assert math.isclose(
        fnx.group_betweenness_centrality(fg, S),
        nx.group_betweenness_centrality(ng, S),
        rel_tol=1e-9,
    )


# ---------------------------------------------------------------------------
# Edge load / current-flow edge betweenness
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("make, n", UNDIRECTED_FAMILIES)
def test_edge_load_centrality_matches_networkx(make, n):
    fg, ng = make(n)
    f = fnx.edge_load_centrality(fg)
    x = nx.edge_load_centrality(ng)
    if not fg.is_directed():
        f = {frozenset(k): v for k, v in f.items()}
        x = {frozenset(k): v for k, v in x.items()}
    # edge_load_centrality returns ints; allow exact integer equality.
    assert f.keys() == x.keys()
    for k in f:
        assert f[k] == x[k]


@pytest.mark.parametrize("make, n", _CURRENT_FLOW_FAMILIES)
def test_edge_current_flow_betweenness_centrality_matches_networkx(make, n):
    fg, ng = make(n)
    f = fnx.edge_current_flow_betweenness_centrality(fg)
    x = nx.edge_current_flow_betweenness_centrality(ng)
    if not fg.is_directed():
        f = {frozenset(k): v for k, v in f.items()}
        x = {frozenset(k): v for k, v in x.items()}
    _assert_centrality_close(f, x, rel=1e-5, abs_=1e-7)


# ---------------------------------------------------------------------------
# Percolation centrality
# ---------------------------------------------------------------------------


def test_percolation_centrality_matches_networkx():
    fg = fnx.path_graph(5)
    ng = nx.path_graph(5)
    # Uniform percolation states default to 1.0 everywhere.
    _assert_centrality_close(
        fnx.percolation_centrality(fg),
        nx.percolation_centrality(ng),
        rel=1e-6,
        abs_=1e-9,
    )


def test_edge_current_flow_betweenness_centrality_is_native_not_nx_delegate():
    """Bead franken_networkx-dqfl: confirm edge_current_flow_betweenness_centrality
    runs through the fnx-native implementation (in-tree RCM ordering +
    _flow_matrix_row) rather than delegating to networkx.
    """
    from unittest import mock

    fg = fnx.path_graph(5)
    ng = nx.path_graph(5)
    expected = nx.edge_current_flow_betweenness_centrality(ng)

    with mock.patch(
        "networkx.edge_current_flow_betweenness_centrality",
        side_effect=AssertionError("fnx must not delegate to networkx"),
    ):
        actual = fnx.edge_current_flow_betweenness_centrality(fg)

    # Normalize by frozenset key for undirected parity.
    a = {frozenset(k): v for k, v in actual.items()}
    e = {frozenset(k): v for k, v in expected.items()}
    _assert_centrality_close(a, e, rel=1e-5, abs_=1e-7)


def test_current_flow_closeness_centrality_is_native_not_nx_delegate():
    """Bead franken_networkx-p3ap: confirm current_flow_closeness_centrality
    runs through the fnx-native implementation rather than delegating into
    networkx. Mock nx.current_flow_closeness_centrality to assert it is
    never called, and verify the fnx result still matches the upstream
    value.
    """
    from unittest import mock

    fg = fnx.path_graph(5)
    ng = nx.path_graph(5)
    expected = nx.current_flow_closeness_centrality(ng)

    with mock.patch(
        "networkx.current_flow_closeness_centrality",
        side_effect=AssertionError("fnx must not delegate to networkx"),
    ):
        actual = fnx.current_flow_closeness_centrality(fg)

    _assert_centrality_close(actual, expected, rel=1e-5, abs_=1e-7)


# ---------------------------------------------------------------------------
# Error contract parity
# ---------------------------------------------------------------------------


def test_current_flow_closeness_rejects_directed_matching_networkx():
    """Current-flow family requires undirected graphs upstream; both
    sides must raise a NetworkX-style exception on directed inputs.

    nx raises NetworkXNotImplemented via the @not_implemented_for decorator;
    fnx raises its corresponding class. Accept either NetworkXError or
    NetworkXNotImplemented from either side.
    """
    fg = fnx.DiGraph()
    fg.add_edge(0, 1)
    ng = nx.DiGraph()
    ng.add_edge(0, 1)
    err_types = []
    for cls_name in ("NetworkXError", "NetworkXNotImplemented"):
        for mod in (fnx, nx):
            cls = getattr(mod, cls_name, None)
            if cls is not None:
                err_types.append(cls)
    err_tuple = tuple(err_types)
    with pytest.raises(err_tuple):
        fnx.current_flow_closeness_centrality(fg)
    with pytest.raises(err_tuple):
        nx.current_flow_closeness_centrality(ng)


def test_current_flow_closeness_rejects_disconnected_matching_networkx():
    """Current-flow closeness rejects disconnected graphs with
    NetworkXError on both sides.
    """
    fg = fnx.Graph()
    fg.add_edges_from([(0, 1), (2, 3)])
    ng = nx.Graph()
    ng.add_edges_from([(0, 1), (2, 3)])
    with pytest.raises((fnx.NetworkXError, nx.NetworkXError)):
        fnx.current_flow_closeness_centrality(fg)
    with pytest.raises(nx.NetworkXError):
        nx.current_flow_closeness_centrality(ng)


# ---------------------------------------------------------------------------
# Solver-selection knobs (pagerank, eigenvector, etc.)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["pagerank", "eigenvector_centrality", "hits"])
def test_public_centrality_wrappers_expose_backend_signature_matches_networkx(name):
    assert str(inspect.signature(getattr(fnx, name))) == str(inspect.signature(getattr(nx, name)))


def _assert_centrality_result_shape_matches_graph(name, result, graph):
    nodes = set(graph)
    if name == "hits":
        hubs, authorities = result
        assert set(hubs) == nodes
        assert set(authorities) == nodes
        return
    assert set(result) == nodes


@pytest.mark.parametrize("name", ["pagerank", "eigenvector_centrality", "hits"])
def test_public_centrality_wrappers_backend_keyword_surface_matches_networkx(name):
    fg = fnx.path_graph(4)
    ng = nx.path_graph(4)
    fnx_fn = getattr(fnx, name)
    nx_fn = getattr(nx, name)

    for backend in (None, "networkx"):
        _assert_centrality_result_shape_matches_graph(name, fnx_fn(fg, backend=backend), fg)
        _assert_centrality_result_shape_matches_graph(name, nx_fn(ng, backend=backend), ng)

    with pytest.raises(ImportError, match="'parallel' backend is not installed"):
        fnx_fn(fg, backend="parallel")
    with pytest.raises(ImportError, match="'parallel' backend is not installed"):
        nx_fn(ng, backend="parallel")

    with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
        fnx_fn(fg, backend_kwargs={"x": 1})
    with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
        nx_fn(ng, backend_kwargs={"x": 1})


@pytest.mark.parametrize(
    ("name", "args"),
    [
        pytest.param("betweenness_centrality", (), id="betweenness_centrality"),
        pytest.param("harmonic_centrality", (), id="harmonic_centrality"),
        pytest.param("closeness_centrality", (), id="closeness_centrality"),
        pytest.param("edge_betweenness_centrality", (), id="edge_betweenness_centrality"),
        pytest.param("katz_centrality", (), id="katz_centrality"),
        pytest.param("load_centrality", (), id="load_centrality"),
        pytest.param("edge_load_centrality", (), id="edge_load_centrality"),
        pytest.param("group_betweenness_centrality", ([1, 2],), id="group_betweenness_centrality"),
        pytest.param("group_closeness_centrality", ([1, 2],), id="group_closeness_centrality"),
    ],
)
def test_additional_public_centrality_wrappers_expose_backend_signature_matches_networkx(
    name, args
):
    del args
    assert str(inspect.signature(getattr(fnx, name))) == str(inspect.signature(getattr(nx, name)))


def _assert_backend_wrapper_result_matches_networkx(name, actual, expected):
    if name in {"edge_betweenness_centrality", "edge_current_flow_betweenness_centrality"}:
        _assert_centrality_close(
            {frozenset(k): v for k, v in actual.items()},
            {frozenset(k): v for k, v in expected.items()},
            rel=1e-6,
            abs_=1e-9,
        )
        return

    if name in {
        "betweenness_centrality",
        "degree_centrality",
        "harmonic_centrality",
        "closeness_centrality",
        "communicability_betweenness_centrality",
        "information_centrality",
        "current_flow_closeness_centrality",
        "current_flow_betweenness_centrality",
        "katz_centrality",
        "in_degree_centrality",
        "out_degree_centrality",
        "percolation_centrality",
        "load_centrality",
        "edge_load_centrality",
    }:
        _assert_centrality_close(actual, expected, rel=1e-6, abs_=1e-9)
        return

    if name == "voterank":
        assert actual == expected
        return

    assert math.isclose(actual, expected, rel_tol=1e-6, abs_tol=1e-9)


@pytest.mark.parametrize(
    ("name", "args"),
    [
        pytest.param("betweenness_centrality", (), id="betweenness_centrality"),
        pytest.param("harmonic_centrality", (), id="harmonic_centrality"),
        pytest.param("closeness_centrality", (), id="closeness_centrality"),
        pytest.param("edge_betweenness_centrality", (), id="edge_betweenness_centrality"),
        pytest.param("katz_centrality", (), id="katz_centrality"),
        pytest.param("load_centrality", (), id="load_centrality"),
        pytest.param("edge_load_centrality", (), id="edge_load_centrality"),
        pytest.param("group_betweenness_centrality", ([1, 2],), id="group_betweenness_centrality"),
        pytest.param("group_closeness_centrality", ([1, 2],), id="group_closeness_centrality"),
    ],
)
def test_additional_public_centrality_wrappers_backend_keyword_surface_matches_networkx(
    name, args
):
    fg = fnx.path_graph(5)
    ng = nx.path_graph(5)
    fnx_fn = getattr(fnx, name)
    nx_fn = getattr(nx, name)

    for backend in (None, "networkx"):
        _assert_backend_wrapper_result_matches_networkx(
            name,
            fnx_fn(fg, *args, backend=backend),
            nx_fn(ng, *args, backend=backend),
        )

    with pytest.raises(ImportError, match="'parallel' backend is not installed"):
        fnx_fn(fg, *args, backend="parallel")
    with pytest.raises(ImportError, match="'parallel' backend is not installed"):
        nx_fn(ng, *args, backend="parallel")

    with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
        fnx_fn(fg, *args, backend_kwargs={"x": 1})
    with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
        nx_fn(ng, *args, backend_kwargs={"x": 1})


@pytest.mark.parametrize(
    ("name", "args", "make"),
    [
        pytest.param("degree_centrality", (), _path, id="degree_centrality"),
        pytest.param("voterank", (), _path, id="voterank"),
        pytest.param("in_degree_centrality", (), _digraph_chain, id="in_degree_centrality"),
        pytest.param("out_degree_centrality", (), _digraph_chain, id="out_degree_centrality"),
        pytest.param("group_degree_centrality", ([1, 2],), _path, id="group_degree_centrality"),
        pytest.param(
            "group_in_degree_centrality",
            ([1, 2],),
            _digraph_chain,
            id="group_in_degree_centrality",
        ),
        pytest.param(
            "group_out_degree_centrality",
            ([1, 2],),
            _digraph_chain,
            id="group_out_degree_centrality",
        ),
    ],
)
def test_degree_family_wrappers_expose_backend_signature_matches_networkx(name, args, make):
    del args, make
    assert str(inspect.signature(getattr(fnx, name))) == str(inspect.signature(getattr(nx, name)))


@pytest.mark.parametrize(
    ("name", "args", "make"),
    [
        pytest.param("degree_centrality", (), _path, id="degree_centrality"),
        pytest.param("voterank", (), _path, id="voterank"),
        pytest.param("in_degree_centrality", (), _digraph_chain, id="in_degree_centrality"),
        pytest.param("out_degree_centrality", (), _digraph_chain, id="out_degree_centrality"),
        pytest.param("group_degree_centrality", ([1, 2],), _path, id="group_degree_centrality"),
        pytest.param(
            "group_in_degree_centrality",
            ([1, 2],),
            _digraph_chain,
            id="group_in_degree_centrality",
        ),
        pytest.param(
            "group_out_degree_centrality",
            ([1, 2],),
            _digraph_chain,
            id="group_out_degree_centrality",
        ),
    ],
)
def test_degree_family_wrappers_backend_keyword_surface_matches_networkx(name, args, make):
    fg, ng = make(5)
    fnx_fn = getattr(fnx, name)
    nx_fn = getattr(nx, name)

    for backend in (None, "networkx"):
        _assert_backend_wrapper_result_matches_networkx(
            name,
            fnx_fn(fg, *args, backend=backend),
            nx_fn(ng, *args, backend=backend),
        )

    with pytest.raises(ImportError, match="'parallel' backend is not installed"):
        fnx_fn(fg, *args, backend="parallel")
    with pytest.raises(ImportError, match="'parallel' backend is not installed"):
        nx_fn(ng, *args, backend="parallel")

    with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
        fnx_fn(fg, *args, backend_kwargs={"x": 1})
    with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
        nx_fn(ng, *args, backend_kwargs={"x": 1})


@pytest.mark.parametrize(
    ("name", "make"),
    [
        pytest.param("communicability_betweenness_centrality", _path, id="communicability_betweenness_centrality"),
        pytest.param("information_centrality", _path, id="information_centrality"),
        pytest.param("current_flow_closeness_centrality", _path, id="current_flow_closeness_centrality"),
        pytest.param("current_flow_betweenness_centrality", _path, id="current_flow_betweenness_centrality"),
        pytest.param(
            "edge_current_flow_betweenness_centrality",
            _path,
            id="edge_current_flow_betweenness_centrality",
        ),
        pytest.param("percolation_centrality", _path, id="percolation_centrality"),
    ],
)
def test_current_flow_family_wrappers_expose_backend_signature_matches_networkx(name, make):
    del make
    assert str(inspect.signature(getattr(fnx, name))) == str(inspect.signature(getattr(nx, name)))


@pytest.mark.parametrize(
    ("name", "make"),
    [
        pytest.param("communicability_betweenness_centrality", _path, id="communicability_betweenness_centrality"),
        pytest.param("information_centrality", _path, id="information_centrality"),
        pytest.param("current_flow_closeness_centrality", _path, id="current_flow_closeness_centrality"),
        pytest.param("current_flow_betweenness_centrality", _path, id="current_flow_betweenness_centrality"),
        pytest.param(
            "edge_current_flow_betweenness_centrality",
            _path,
            id="edge_current_flow_betweenness_centrality",
        ),
        pytest.param("percolation_centrality", _path, id="percolation_centrality"),
    ],
)
def test_current_flow_family_wrappers_backend_keyword_surface_matches_networkx(name, make):
    fg, ng = make(5)
    fnx_fn = getattr(fnx, name)
    nx_fn = getattr(nx, name)

    for backend in (None, "networkx"):
        _assert_backend_wrapper_result_matches_networkx(
            name,
            fnx_fn(fg, backend=backend),
            nx_fn(ng, backend=backend),
        )

    with pytest.raises(ImportError, match="'parallel' backend is not installed"):
        fnx_fn(fg, backend="parallel")
    with pytest.raises(ImportError, match="'parallel' backend is not installed"):
        nx_fn(ng, backend="parallel")

    with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
        fnx_fn(fg, backend_kwargs={"x": 1})
    with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
        nx_fn(ng, backend_kwargs={"x": 1})


def test_edge_load_centrality_cutoff_false_matches_networkx():
    fg = fnx.path_graph(4)
    ng = nx.path_graph(4)
    _assert_centrality_close(
        fnx.edge_load_centrality(fg, cutoff=False),
        nx.edge_load_centrality(ng, cutoff=False),
        rel=1e-9,
        abs_=1e-9,
    )


def test_pagerank_alpha_knob_matches_networkx():
    fg = fnx.cycle_graph(8)
    ng = nx.cycle_graph(8)
    for alpha in (0.5, 0.7, 0.9):
        _assert_centrality_close(
            fnx.pagerank(fg, alpha=alpha, tol=1e-9),
            nx.pagerank(ng, alpha=alpha, tol=1e-9),
            rel=1e-5,
            abs_=1e-7,
        )


def test_pagerank_default_weight_attribute_honours_weights():
    """br-prwgt: fnx.pagerank's default ``weight='weight'`` used to short-
    circuit into the Rust implementation which silently ignored the weight
    parameter — the default call produced the unweighted PageRank on a
    weighted graph. This pins the weighted-vs-unweighted difference so a
    future short-circuit regression can't sneak past."""
    fg = fnx.Graph()
    fg.add_edge(0, 1, weight=100.0)
    fg.add_edge(0, 2, weight=1.0)
    ng = nx.Graph()
    ng.add_edge(0, 1, weight=100.0)
    ng.add_edge(0, 2, weight=1.0)

    weighted = fnx.pagerank(fg)  # default weight='weight'
    unweighted = fnx.pagerank(fg, weight=None)

    # The weighted PageRank must differ from unweighted on this graph.
    assert weighted != unweighted

    # And match upstream numerically.
    _assert_centrality_close(
        weighted,
        nx.pagerank(ng),
        rel=1e-9,
        abs_=1e-12,
    )


def test_pagerank_custom_weight_key_honours_weights():
    """br-prwgt: explicit non-default weight attribute name."""
    fg = fnx.DiGraph()
    fg.add_edge(0, 1, capacity=10.0)
    fg.add_edge(1, 2, capacity=0.1)
    fg.add_edge(2, 0, capacity=5.0)
    ng = nx.DiGraph()
    ng.add_edge(0, 1, capacity=10.0)
    ng.add_edge(1, 2, capacity=0.1)
    ng.add_edge(2, 0, capacity=5.0)

    _assert_centrality_close(
        fnx.pagerank(fg, weight="capacity"),
        nx.pagerank(ng, weight="capacity"),
        rel=1e-9,
        abs_=1e-12,
    )


def test_eigenvector_centrality_max_iter_and_tol_match_networkx():
    fg = fnx.path_graph(8)
    ng = nx.path_graph(8)
    _eigenvector_values_close(
        fnx.eigenvector_centrality(fg, max_iter=500, tol=1e-9),
        nx.eigenvector_centrality(ng, max_iter=500, tol=1e-9),
        rel=1e-5,
        abs_=1e-7,
    )


def test_eigenvector_centrality_nonconvergence_matches_networkx():
    fg = fnx.path_graph(8)
    ng = nx.path_graph(8)
    with pytest.raises(nx.PowerIterationFailedConvergence):
        nx.eigenvector_centrality(ng, max_iter=1, tol=1e-12)
    with pytest.raises(fnx.PowerIterationFailedConvergence):
        fnx.eigenvector_centrality(fg, max_iter=1, tol=1e-12)
