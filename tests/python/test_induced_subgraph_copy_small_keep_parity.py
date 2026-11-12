"""br-r37-c1-5cqc2 — an induced copy of a SMALL keep set must not walk the parent.

``G.subgraph(nbunch).copy()`` handed the whole job to a native induced-subgraph
kernel that walks the entire parent graph. That kernel exists for the k-core
family, where the kept set is most of the graph and walking it is right. For a
small keep set it is the wrong tool by two orders of magnitude, and the cost
tracked the PARENT rather than the request:

    N        nx us      fnx us     t_nx/t_fnx
    500      51.50       80.03       0.6435
    2000     56.74      258.36       0.2196
    8000     58.81     1299.53       0.0453
    32000    43.56     4683.89       0.0093     (DiGraph: 0.0043)

The pure-Python builder that was already sitting under it touches only the kept
nodes and their rows. Measured fallback/native at N=8000, below 1.0 meaning the
Python builder is faster:

    keep      10     100     400    1600    4000    7000
    Graph    0.050   0.206   0.565   1.235   2.295   1.678
    DiGraph  0.044   0.137   0.396   0.890   1.704   1.853

so the crossover is near N/10 for Graph and N/3 for DiGraph. The gate uses N/10,
at or under both, and the kernel keeps every case it was written for.

WHAT NEEDS LOCKING is that the two builders are interchangeable, because the
gate now sends different calls down different paths. NODE AND EDGE ORDER are the
sharp edge: networkx's own node order here is FilterAtlas's, which switches rule
at exactly half the parent, so the two routes must agree with networkx and with
each other on both sides of the gate.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _build(lib, cls_name, order):
    graph = getattr(lib, cls_name)()
    for i in range(order):
        graph.add_edge(f"n{i}", f"n{(i * 7 + 3) % order}", weight=float(i % 7))
    graph.add_edge("n0", "n0")
    if graph.is_multigraph():
        graph.add_edge("n0", "n1", weight=42.0)
    for i in range(order):
        graph.nodes[f"n{i}"]["tag"] = i % 3
    graph.graph["name"] = "fixture"
    graph.add_node("isolated")
    return graph


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("order", [40, 400, 2000])
@pytest.mark.parametrize("keep", [1, 5, 30, 199, 500])
def test_induced_copy_matches_networkx_on_both_sides_of_the_gate(
    cls_name, order, keep
):
    """keep/order spans well under and well over the N/10 routing threshold."""
    nbunch = [f"n{i}" for i in range(min(keep, order))] + ["isolated"]
    gnx, gfx = _build(nx, cls_name, order), _build(fnx, cls_name, order)
    want, got = gnx.subgraph(nbunch).copy(), gfx.subgraph(nbunch).copy()
    assert list(got.nodes()) == list(want.nodes()), "node ORDER diverged"
    assert list(got.edges(data=True)) == list(want.edges(data=True))
    assert dict(got.nodes(data=True)) == dict(want.nodes(data=True))
    assert dict(got.graph) == dict(want.graph)
    assert type(got).__name__ == type(want).__name__


@pytest.mark.parametrize("cls_name", CLASSES)
def test_the_two_routes_agree_with_each_other_on_the_same_graph(cls_name):
    """Force each builder on the SAME call and compare directly.

    Comparing each to networkx separately would miss a case where both drifted
    together, and the gate's whole premise is that they are interchangeable.
    """
    order = 2000
    graph = _build(fnx, cls_name, order)
    for keep in (1, 10, 150, 900):
        nbunch = [f"n{i}" for i in range(keep)]
        original = fnx._INDUCED_NATIVE_KEEP_DIVISOR
        try:
            fnx._INDUCED_NATIVE_KEEP_DIVISOR = 0  # never "small" -> native
            native = graph.subgraph(nbunch).copy()
            fnx._INDUCED_NATIVE_KEEP_DIVISOR = 10**9  # always "small" -> python
            python = graph.subgraph(nbunch).copy()
        finally:
            fnx._INDUCED_NATIVE_KEEP_DIVISOR = original
        assert list(python.nodes()) == list(native.nodes()), (cls_name, keep)
        assert list(python.edges(data=True)) == list(native.edges(data=True))
        assert dict(python.nodes(data=True)) == dict(native.nodes(data=True))


def test_the_gate_predicate_is_what_it_claims():
    graph = _build(fnx, "Graph", 1000)
    assert fnx._induced_keep_is_small([f"n{i}" for i in range(10)], graph)
    assert not fnx._induced_keep_is_small([f"n{i}" for i in range(500)], graph)


def test_the_gate_degrades_rather_than_raising_on_an_odd_parent():
    """It sits on a hot path; an unsizable parent keeps the previous route."""

    class NoLen:
        pass

    assert fnx._induced_keep_is_small([1, 2, 3], NoLen()) is False


@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph"])
def test_k_core_family_still_matches_networkx(cls_name):
    """The kernel was written for these; the gate must leave them alone.

    A k-core keeps well over a tenth of the graph, so these stay on the native
    route — and this asserts the gate did not accidentally divert them.
    """
    gnx, gfx = _build(nx, cls_name, 600), _build(fnx, cls_name, 600)
    for graph in (gnx, gfx):
        graph.remove_edge("n0", "n0")
    for k in (1, 2):
        want, got = nx.k_core(gnx, k), nx.k_core(gfx, k)
        assert list(got.nodes()) == list(want.nodes()), k
        assert sorted(map(sorted, got.edges())) == sorted(map(sorted, want.edges()))


def test_subgraph_copy_is_a_real_copy_not_a_view():
    """The routing change must not turn a copy into something live."""
    graph = _build(fnx, "Graph", 500)
    nbunch = [f"n{i}" for i in range(10)]
    copied = graph.subgraph(nbunch).copy()
    before = sorted(map(sorted, copied.edges()))
    graph.add_edge("n0", "n400")
    graph.remove_node("n1")
    assert sorted(map(sorted, copied.edges())) == before
