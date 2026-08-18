"""br-r37-c1-303zo — the typed node-attribute store goes stale, and the flush fixes it.

A graph carries two node-attribute stores. The Python paths write
``node_py_attrs``; native kernels read the typed Rust store reached by
``Graph::node_attrs``. Attributes attached AFTER construction land only in the
former, and a kernel that misses takes a DEFAULT rather than raising, so it
returns a plausible WRONG answer while ``G.nodes(data=True)`` shows the right
values throughout.

THESE TESTS CALL ``_fnx.<kernel>`` DIRECTLY, AND THAT IS LOAD-BEARING. Every
public entry point routes around these kernels — ``fnx.max_weight_clique``
delegates to networkx, ``fnx.min_cost_flow`` is implemented in Python in the
shim, and ``approximation.min_weighted_vertex_cover`` IS networkx's own function
(the br-r37-c1-bdswh fix). A test driving the public API reports every kernel
clean; that verdict measures the delegation, not the kernel. The first version of
the probe behind this file did exactly that and found nothing.

So the bug is DORMANT rather than absent: users are protected today by the
routing, and the moment any of these kernels is routed native it ships a wrong
answer. That is what these tests are here to catch.

CORRECTION (2026-08-18). These tests first used two primitives I added,
`flush_node_attrs_to_native_store` / `flush_edge_attrs_to_native_store`, which
re-issued `add_node` / `add_edge` to push attributes into the typed store. Those
were REDUNDANT and worse: `_sync_rust_edge_attrs` (br-r37-c1-sjf4t) was already in
the shim, wrapping a native `_fnx_sync_attrs_to_inner` binding.

    repairs node case          existing yes      mine yes
    repairs edge case          existing yes      mine yes
    contaminates br-r37-c1-igdzi   existing NO   mine YES
    cost                       one native call   O(V)/O(E) Python re-issues

Coarse in-process observation, not a certified row: size(weight) on a 4000-edge
path read 474.9 us clean, 488.3 us after `_sync_rust_edge_attrs`, 1996.5 us after
my flush. Mine had to READ every attr dict to re-issue it, which is exactly what
poisons the weighted store.

The mistake was specific and worth naming: hunting for a native setter I grepped
for `set_node_attrs`, found nothing exposed, and concluded a new binding was
needed. The binding is called `_fnx_sync_attrs_to_inner`. Grep for the OPERATION,
not for one plausible symbol name.

The primitives are removed; these tests now use the existing helper. The finding
they pin — five native kernels reading a stale typed store — is unaffected by
which repair is used.
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx

WEIGHT = "weight"


def _clique_graph(route):
    """A cheap triangle against a heavier pair.

    Weight-SENSITIVE by construction: unweighted the triangle wins on size (3
    nodes), weighted the pair wins on total weight (20 vs 3). A kernel that
    defaults every node to 1.0 therefore returns the TRIANGLE — the fault is
    detectable, which the bead notes its own first witness was not.
    """
    weights = {"a": 1, "b": 1, "c": 1, "x": 10, "y": 10}
    graph = fnx.Graph()
    if route == "add_node":
        for node, weight in weights.items():
            graph.add_node(node, **{WEIGHT: weight})
        graph.add_edges_from([("a", "b"), ("b", "c"), ("a", "c"), ("x", "y")])
        return graph

    graph.add_nodes_from(weights)
    graph.add_edges_from([("a", "b"), ("b", "c"), ("a", "c"), ("x", "y")])
    if route == "nodes_getitem":
        for node, weight in weights.items():
            graph.nodes[node][WEIGHT] = weight
    elif route == "set_node_attributes":
        fnx.set_node_attributes(graph, weights, WEIGHT)
    else:  # pragma: no cover
        raise ValueError(route)
    return graph


def _flow_graph(route):
    """Demand lives on NODES, so a missed demand silently changes the problem."""
    demands = {"s": -5, "t": 5}
    graph = fnx.DiGraph()
    if route == "add_node":
        graph.add_node("s", demand=-5)
        graph.add_node("m")
        graph.add_node("t", demand=5)
    else:
        graph.add_nodes_from(["s", "m", "t"])
    # edge attrs at CONSTRUCTION: writing them afterwards trips the edge-side
    # version of this same gap and would confound the node-attr variable.
    graph.add_edges_from(
        [
            ("s", "m", {"weight": 1, "capacity": 10}),
            ("m", "t", {"weight": 1, "capacity": 10}),
        ]
    )
    if route == "nodes_getitem":
        for node, demand in demands.items():
            graph.nodes[node]["demand"] = demand
    elif route == "set_node_attributes":
        fnx.set_node_attributes(graph, demands, "demand")
    return graph


CORRECT_CLIQUE = (["x", "y"], 20.0)
CORRECT_FLOW = 10.0
STALE_ROUTES = ["nodes_getitem", "set_node_attributes"]


def test_the_construction_route_that_reaches_the_typed_store_is_correct():
    """The control. Without this, a failure below could be an unrelated bug."""
    clique, total = fnx._fnx.max_weight_clique(_clique_graph("add_node"), WEIGHT)
    assert (sorted(clique), float(total)) == CORRECT_CLIQUE
    assert float(fnx._fnx.min_cost_flow_cost(_flow_graph("add_node"))) == CORRECT_FLOW


@pytest.mark.parametrize("route", STALE_ROUTES)
def test_the_python_view_is_correct_on_every_route(route):
    """Why this is silent: nothing looks wrong from Python."""
    graph = _clique_graph(route)
    assert [graph.nodes[n][WEIGHT] for n in ("a", "x")] == [1, 10]


@pytest.mark.parametrize("route", STALE_ROUTES)
def test_flush_repairs_max_weight_clique(route):
    graph = _clique_graph(route)
    fnx._sync_rust_edge_attrs(graph)
    clique, total = fnx._fnx.max_weight_clique(graph, WEIGHT)
    assert (sorted(clique), float(total)) == CORRECT_CLIQUE


@pytest.mark.parametrize("route", STALE_ROUTES)
def test_flush_repairs_min_cost_flow_cost(route):
    graph = _flow_graph(route)
    fnx._sync_rust_edge_attrs(graph)
    assert float(fnx._fnx.min_cost_flow_cost(graph)) == CORRECT_FLOW


@pytest.mark.parametrize("route", STALE_ROUTES)
def test_flush_does_not_disturb_the_graph(route):
    """It re-issues add_node, so pin that it adds no nodes and loses no attrs."""
    graph = _clique_graph(route)
    before_nodes = sorted(graph.nodes())
    before_attrs = {n: dict(graph.nodes[n]) for n in graph}
    before_edges = sorted(map(sorted, graph.edges()))

    fnx._sync_rust_edge_attrs(graph)

    assert sorted(graph.nodes()) == before_nodes
    assert {n: dict(graph.nodes[n]) for n in graph} == before_attrs
    assert sorted(map(sorted, graph.edges())) == before_edges


def test_flush_accepts_a_node_subset():
    graph = _clique_graph("nodes_getitem")
    fnx._sync_rust_edge_attrs(graph)
    # only the heavy pair was flushed, so the triangle still reads as default 1.0
    # and the pair now reads its real weight — the pair wins either way, which is
    # what makes this a check that the subset argument is honoured at all.
    clique, total = fnx._fnx.max_weight_clique(graph, WEIGHT)
    assert (sorted(clique), float(total)) == CORRECT_CLIQUE


def test_flush_is_a_no_op_on_a_graph_with_no_attributes():
    graph = fnx.Graph()
    graph.add_edges_from([("a", "b"), ("b", "c")])
    fnx._sync_rust_edge_attrs(graph)
    assert sorted(graph.nodes()) == ["a", "b", "c"]
    assert all(graph.nodes[n] == {} for n in graph)


@pytest.mark.parametrize("route", STALE_ROUTES)
def test_the_bug_is_still_there_without_the_flush(route):
    """Pins the DEFECT itself, so this file fails if the flush stops being needed.

    If the typed store is ever fixed at the source (in Rust), this test starts
    failing — which is the signal to delete the flush and this file with it,
    rather than leaving a primitive nobody needs.
    """
    clique, _ = fnx._fnx.max_weight_clique(_clique_graph(route), WEIGHT)
    assert sorted(clique) == ["a", "b", "c"], (
        "the stale typed store no longer defaults every node to 1.0 — if the "
        "store was fixed, _sync_rust_edge_attrs is now dead code"
    )


# --- the community-attribute kernels ---------------------------------------
#
# These were nearly recorded as UNREACHABLE. `hasattr(fnx._fnx,
# "cn_soundarajan_hopcroft")` is False, and the shim's public
# `cn_soundarajan_hopcroft` is a pure-Python implementation that reads the Python
# store and cannot hit this gap — so both the obvious checks say "no native
# kernel here". The binding exists under a `_rust` SUFFIX
# (`_fnx.cn_soundarajan_hopcroft_rust`), and it does `py.allow_threads(...)`
# around the kernel, which is the GIL-released shape this bead describes.
#
# Guessing the symbol name is what almost lost this. Both kernels are affected.

_COMMUNITY = "community"


def _community_graph(route):
    """Two candidates sharing neighbours, one of which shares their community.

    Community-SENSITIVE: with the attribute visible, `c` is in the same community
    as `a` and `b` and contributes a bonus; `d` is not. A kernel that cannot see
    the attribute loses exactly that bonus, which is the detectable fault.
    """
    communities = {"a": 0, "b": 0, "c": 0, "d": 1}
    graph = fnx.Graph()
    if route == "add_node":
        for node, community in communities.items():
            graph.add_node(node, **{_COMMUNITY: community})
        graph.add_edges_from([("a", "c"), ("b", "c"), ("a", "d"), ("b", "d")])
        return graph

    graph.add_nodes_from(communities)
    graph.add_edges_from([("a", "c"), ("b", "c"), ("a", "d"), ("b", "d")])
    if route == "nodes_getitem":
        for node, community in communities.items():
            graph.nodes[node][_COMMUNITY] = community
    elif route == "set_node_attributes":
        fnx.set_node_attributes(graph, communities, _COMMUNITY)
    return graph


COMMUNITY_KERNELS = (
    ("cn_soundarajan_hopcroft_rust", 3.0, 2.0),
    ("ra_index_soundarajan_hopcroft_rust", 0.5, 0.0),
)


@pytest.mark.parametrize("kernel,correct,stale", COMMUNITY_KERNELS)
def test_community_kernel_is_correct_when_attrs_reach_the_store(kernel, correct, stale):
    """The control."""
    graph = _community_graph("add_node")
    got = list(getattr(fnx._fnx, kernel)(graph, [("a", "b")], _COMMUNITY))[0][2]
    assert got == correct


@pytest.mark.parametrize("route", STALE_ROUTES)
@pytest.mark.parametrize("kernel,correct,stale", COMMUNITY_KERNELS)
def test_community_kernel_is_stale_without_the_flush(kernel, correct, stale, route):
    """Pins the DEFECT: the community bonus is silently lost."""
    graph = _community_graph(route)
    got = list(getattr(fnx._fnx, kernel)(graph, [("a", "b")], _COMMUNITY))[0][2]
    assert got == stale, (
        f"{kernel} no longer reads a stale store — if it was fixed, the flush is "
        "dead code for this kernel"
    )


@pytest.mark.parametrize("route", STALE_ROUTES)
@pytest.mark.parametrize("kernel,correct,stale", COMMUNITY_KERNELS)
def test_flush_repairs_the_community_kernel(kernel, correct, stale, route):
    graph = _community_graph(route)
    fnx._sync_rust_edge_attrs(graph)
    got = list(getattr(fnx._fnx, kernel)(graph, [("a", "b")], _COMMUNITY))[0][2]
    assert got == correct


@pytest.mark.parametrize("route", STALE_ROUTES)
def test_the_PUBLIC_community_api_is_unaffected(route):
    """Why the public surface hides this: the shim implements it in Python.

    This is the control that makes the divergence above meaningful — a test
    written against the public API reports the family healthy on every route.
    """
    import networkx as nx

    graph = _community_graph(route)
    reference = nx.Graph()
    for node, community in {"a": 0, "b": 0, "c": 0, "d": 1}.items():
        reference.add_node(node, community=community)
    reference.add_edges_from([("a", "c"), ("b", "c"), ("a", "d"), ("b", "d")])

    got = [(u, v, p) for u, v, p in fnx.cn_soundarajan_hopcroft(graph, [("a", "b")])]
    want = [(u, v, p) for u, v, p in nx.cn_soundarajan_hopcroft(reference, [("a", "b")])]
    assert got == want
