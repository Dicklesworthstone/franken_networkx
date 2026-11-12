"""`check_planarity(counterexample=True)` must return the same type as its sibling.

br-r37-c1-rcg8f. `franken_networkx/planarity.py` promises in its own docstring
that its overrides "return fnx graph types instead of NetworkX graphs", and
`get_counterexample` honoured that while `check_planarity(counterexample=True)`
returned a `networkx.classes.graph.Graph` — one module, one mathematical object,
two types depending on which entry point you used.

The convention this settles on is not invented here: `complete_to_chordal_graph`,
`subgraph().copy()`, `k_core` and `get_counterexample` all return fnx types.

Values were never in question and are re-asserted against live networkx anyway,
because a type conversion is exactly the kind of change that can quietly drop
attributes.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx
from franken_networkx import planarity as fnx_planarity

_NONPLANAR = [
    pytest.param(lambda m: m.complete_graph(5), id="K5"),
    pytest.param(lambda m: m.complete_bipartite_graph(3, 3), id="K33"),
    pytest.param(lambda m: m.complete_graph(6), id="K6"),
]

_PLANAR = [
    pytest.param(lambda m: m.path_graph(4), id="path"),
    pytest.param(lambda m: m.cycle_graph(5), id="cycle"),
    pytest.param(lambda m: m.complete_graph(4), id="K4"),
]


@pytest.mark.parametrize("build", _NONPLANAR)
def test_counterexample_type_matches_get_counterexample(build):
    """The inconsistency this bead was filed for, stated directly."""
    graph = build(fnx)
    from_check = fnx_planarity.check_planarity(graph, counterexample=True)[1]
    from_getter = fnx_planarity.get_counterexample(graph)

    # Exact type identity IS the assertion here: the two entry points must return
    # the SAME concrete class. isinstance would pass a Graph/MultiGraph mismatch,
    # which is precisely the divergence being tested for.
    assert type(from_check) is type(from_getter)  # ubs:ignore py.type-equality
    assert isinstance(from_check, (fnx.Graph, fnx.DiGraph, fnx.MultiGraph, fnx.MultiDiGraph))


@pytest.mark.parametrize("build", _NONPLANAR)
def test_counterexample_matches_networkx_structurally(build):
    """Converting the type must not change the subgraph."""
    actual = fnx_planarity.check_planarity(build(fnx), counterexample=True)[1]
    expected = nx.check_planarity(build(nx), counterexample=True)[1]

    assert sorted(actual.nodes()) == sorted(expected.nodes())
    assert sorted(map(sorted, actual.edges())) == sorted(map(sorted, expected.edges()))


def test_counterexample_conversion_preserves_attributes():
    """A graph conversion is where attributes go missing; check they do not."""
    fnx_graph, nx_graph = fnx.complete_graph(5), nx.complete_graph(5)
    for u, v in list(nx_graph.edges()):
        fnx_graph[u][v]["w"] = u * 10 + v
        nx_graph[u][v]["w"] = u * 10 + v
    for node in list(nx_graph.nodes()):
        fnx_graph.nodes[node]["tag"] = str(node)
        nx_graph.nodes[node]["tag"] = str(node)

    actual = fnx_planarity.check_planarity(fnx_graph, counterexample=True)[1]
    expected = nx.check_planarity(nx_graph, counterexample=True)[1]

    assert {n: dict(actual.nodes[n]) for n in actual.nodes()} == {
        n: dict(expected.nodes[n]) for n in expected.nodes()
    }
    assert all(dict(actual[u][v]) == dict(expected[u][v]) for u, v in expected.edges())
    assert dict(actual.graph) == dict(expected.graph)


@pytest.mark.parametrize("build", _PLANAR)
@pytest.mark.parametrize("counterexample", [False, True])
def test_planar_certificate_stays_a_networkx_planar_embedding(build, counterexample):
    """The gate is exact: the PLANAR branch must NOT be converted.

    Its certificate is a `PlanarEmbedding`, kept as networkx's class on purpose so
    `isinstance` and `check_structure()` keep working. Converting it would break
    both, which is why the conversion is gated on `is_planar` being False rather
    than on "the certificate is a graph".
    """
    is_planar, certificate = fnx_planarity.check_planarity(
        build(fnx), counterexample=counterexample
    )
    assert is_planar
    assert isinstance(certificate, nx.PlanarEmbedding)
    certificate.check_structure()


@pytest.mark.parametrize("build", _NONPLANAR)
def test_no_certificate_requested_still_returns_none(build):
    """Without `counterexample=True` a non-planar graph certifies as None, as nx."""
    assert fnx_planarity.check_planarity(build(fnx), counterexample=False) == (
        False,
        None,
    )
    assert nx.check_planarity(build(nx), counterexample=False) == (False, None)


@pytest.mark.parametrize("build", _NONPLANAR)
def test_top_level_and_namespace_agree(build):
    """Both spellings must return the same type — the dual-path hazard."""
    graph = build(fnx)
    top_level = fnx.check_planarity(graph, counterexample=True)[1]
    namespace = fnx_planarity.check_planarity(graph, counterexample=True)[1]
    # Same reasoning as above: concrete-class identity, not isinstance.
    assert type(top_level) is type(namespace)  # ubs:ignore py.type-equality


def test_recursive_variant_is_networkxs_own_function_and_returns_nx_types():
    """Documented residual, asserted so it is a decision rather than a surprise.

    `franken_networkx.planarity.check_planarity_recursive` is bound directly to
    `networkx.algorithms.planarity.check_planarity_recursive` — a deliberate
    choice recorded under br-r37-c1-56nd2, since upstream already handles backend
    dispatch. It therefore returns networkx types, unlike the non-recursive
    entry point above. That is exact nx parity for that name, at the cost of
    internal consistency; if it is ever wrapped, this test should be the thing
    that fails and prompts the update.
    """
    import networkx.algorithms.planarity as nx_planarity

    assert (
        fnx_planarity.check_planarity_recursive
        is nx_planarity.check_planarity_recursive
    )
    certificate = fnx_planarity.check_planarity_recursive(
        fnx.complete_graph(5), counterexample=True
    )[1]
    assert type(certificate).__module__.startswith("networkx")
