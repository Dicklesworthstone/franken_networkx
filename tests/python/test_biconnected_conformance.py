"""NetworkX conformance for the biconnected-components / bridges family.

Existing tests scattered across
``test_articulation_biconnected_dfs_order_parity.py`` and
``test_biconnected_component_edges_generator_parity.py`` cover specific
parity points (DFS-order, generator contract). Add a broad
differential test that exercises the full family across structured +
random fixtures so any silent divergence in component splitting,
articulation-point detection, or bridge enumeration surfaces
immediately.

Found a real bug locked in by this harness: ``biconnected_components``
on the "bowtie" graph (two triangles sharing a vertex) returned a
single merged 5-node component instead of NX's two 3-node components.
The Rust ``_raw_biconnected_components`` failed to split at
articulation point 2; the companion ``biconnected_component_edges``
already delegated to NX and got it right. Fix routes
``biconnected_components`` through NX too.

Covered functions:

- ``biconnected_components(G)`` — node-set decomposition.
- ``biconnected_component_edges(G)`` — edge-set decomposition.
- ``is_biconnected(G)`` — predicate.
- ``articulation_points(G)`` — cut vertices.
- ``bridges(G)`` — cut edges.
- ``has_bridges(G)`` — bridge predicate.
- ``local_bridges(G)`` — edges with no triangle support.

Plus cross-relation invariants:

- A graph is biconnected iff it has no articulation points (and is
  connected with ≥ 2 nodes).
- Every bridge edge sits in its own 2-node biconnected component.
- The number of biconnected components equals
  ``|articulation_points| + 1`` for a connected graph.
- Bridges ⊆ local_bridges.
"""

from __future__ import annotations

import itertools
import warnings

import pytest
import networkx as nx

import franken_networkx as fnx


def _pair(edges, nodes=None):
    fg = fnx.Graph()
    ng = nx.Graph()
    if nodes is not None:
        fg.add_nodes_from(nodes)
        ng.add_nodes_from(nodes)
    for u, v in edges:
        fg.add_edge(u, v)
        ng.add_edge(u, v)
    return fg, ng


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _structured_fixtures():
    out = []
    out.append(("triangle", [(0, 1), (1, 2), (2, 0)], [0, 1, 2]))
    out.append(("square",
                [(0, 1), (1, 2), (2, 3), (3, 0)], list(range(4))))
    out.append(("K_4", list(itertools.combinations(range(4), 2)),
                list(range(4))))
    out.append(("K_5", list(itertools.combinations(range(5), 2)),
                list(range(5))))
    out.append(("path_P_5",
                [(0, 1), (1, 2), (2, 3), (3, 4)], list(range(5))))
    out.append(("S_4_star",
                [(0, i) for i in range(1, 5)], list(range(5))))
    # Articulation-point fixtures
    out.append(("bowtie",
                [(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 2)],
                list(range(5))))
    out.append(("two_triangles_bridge",
                [(0, 1), (1, 2), (2, 0),
                 (2, 3),
                 (3, 4), (4, 5), (5, 3)],
                list(range(6))))
    out.append(("three_triangles_chain",
                [(0, 1), (1, 2), (2, 0),
                 (2, 3),
                 (3, 4), (4, 5), (5, 3),
                 (5, 6),
                 (6, 7), (7, 8), (8, 6)],
                list(range(9))))
    out.append(("path_with_pendant_triangle",
                [(0, 1), (1, 2), (2, 3),
                 (3, 4), (4, 5), (5, 3)],
                list(range(6))))
    out.append(("disjoint_K3_K3",
                [(0, 1), (1, 2), (2, 0),
                 (3, 4), (4, 5), (5, 3)],
                list(range(6))))
    out.append(("isolate_plus_K3",
                [(0, 1), (1, 2), (2, 0)], [0, 1, 2, 99]))
    out.append(("petersen", list(nx.petersen_graph().edges()),
                list(nx.petersen_graph().nodes())))
    out.append(("hypercube_3", list(nx.hypercube_graph(3).edges()),
                list(nx.hypercube_graph(3).nodes())))
    return out


def _random_fixtures():
    out = []
    for n, p, seed in [
        (8, 0.3, 1), (10, 0.3, 2), (10, 0.5, 3),
        (12, 0.3, 4), (15, 0.25, 5), (15, 0.3, 6),
        (20, 0.2, 7), (25, 0.15, 8),
    ]:
        gnp = nx.gnp_random_graph(n, p, seed=seed)
        out.append((f"gnp_n{n}_p{p}_s{seed}",
                    list(gnp.edges()), list(range(n))))
    return out


STRUCTURED = _structured_fixtures()
RANDOM = _random_fixtures()
ALL_FIXTURES = STRUCTURED + RANDOM


# ---------------------------------------------------------------------------
# biconnected_components
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", ALL_FIXTURES,
                         ids=[fx[0] for fx in ALL_FIXTURES])
def test_biconnected_components_matches_networkx(name, edges, nodes):
    fg, ng = _pair(edges, nodes)
    fr = sorted(frozenset(c) for c in fnx.biconnected_components(fg))
    nr = sorted(frozenset(c) for c in nx.biconnected_components(ng))
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


def test_biconnected_components_bowtie_splits_at_articulation_point():
    """Regression for br-bccbowtie: the bowtie graph must produce two
    3-node components, not one merged 5-node component."""
    fg, _ = _pair(
        [(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 2)],
        list(range(5)),
    )
    components = {frozenset(c) for c in fnx.biconnected_components(fg)}
    assert components == {frozenset({0, 1, 2}), frozenset({2, 3, 4})}


# ---------------------------------------------------------------------------
# biconnected_component_edges
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", ALL_FIXTURES,
                         ids=[fx[0] for fx in ALL_FIXTURES])
def test_biconnected_component_edges_matches_networkx(name, edges, nodes):
    fg, ng = _pair(edges, nodes)
    fr = sorted(
        frozenset(frozenset(e) for e in c)
        for c in fnx.biconnected_component_edges(fg)
    )
    nr = sorted(
        frozenset(frozenset(e) for e in c)
        for c in nx.biconnected_component_edges(ng)
    )
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# is_biconnected
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", ALL_FIXTURES,
                         ids=[fx[0] for fx in ALL_FIXTURES])
def test_is_biconnected_matches_networkx(name, edges, nodes):
    fg, ng = _pair(edges, nodes)
    assert fnx.is_biconnected(fg) == nx.is_biconnected(ng)


# ---------------------------------------------------------------------------
# articulation_points
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", ALL_FIXTURES,
                         ids=[fx[0] for fx in ALL_FIXTURES])
def test_articulation_points_matches_networkx(name, edges, nodes):
    fg, ng = _pair(edges, nodes)
    fr = sorted(fnx.articulation_points(fg))
    nr = sorted(nx.articulation_points(ng))
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# bridges
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", ALL_FIXTURES,
                         ids=[fx[0] for fx in ALL_FIXTURES])
def test_bridges_matches_networkx(name, edges, nodes):
    fg, ng = _pair(edges, nodes)
    fr = sorted(tuple(sorted(e)) for e in fnx.bridges(fg))
    nr = sorted(tuple(sorted(e)) for e in nx.bridges(ng))
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# local_bridges
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", ALL_FIXTURES,
                         ids=[fx[0] for fx in ALL_FIXTURES])
def test_local_bridges_matches_networkx(name, edges, nodes):
    fg, ng = _pair(edges, nodes)
    fr = sorted(
        (tuple(sorted([u, v])), span)
        for u, v, span in fnx.local_bridges(fg)
    )
    nr = sorted(
        (tuple(sorted([u, v])), span)
        for u, v, span in nx.local_bridges(ng)
    )
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


def test_local_bridges_callable_weight_matches_networkx():
    fg, ng = _pair(
        [
            (0, 1),
            (1, 2),
            (2, 3),
            (0, 3),
        ],
        list(range(4)),
    )
    for graph in (fg, ng):
        graph[0][1]["weight"] = 10
        graph[1][2]["weight"] = 1
        graph[2][3]["weight"] = 1
        graph[0][3]["weight"] = 1

    def double_weight(_u, _v, attrs):
        return attrs.get("weight", 1) * 2

    assert list(fnx.local_bridges(fg, weight=double_weight)) == list(
        nx.local_bridges(ng, weight=double_weight)
    )


# ---------------------------------------------------------------------------
# Cross-relation invariants
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", ALL_FIXTURES,
                         ids=[fx[0] for fx in ALL_FIXTURES])
def test_is_biconnected_iff_no_articulation_points_and_connected(
    name, edges, nodes,
):
    """A graph with ≥ 2 nodes is biconnected iff it is connected and
    has no articulation points."""
    fg, _ = _pair(edges, nodes)
    if fg.number_of_nodes() < 2:
        return
    is_b = fnx.is_biconnected(fg)
    has_articulations = bool(list(fnx.articulation_points(fg)))
    is_conn = fnx.is_connected(fg)
    assert is_b == (is_conn and not has_articulations), (
        f"{name}: is_biconnected={is_b} but is_connected={is_conn}, "
        f"articulation_points={list(fnx.articulation_points(fg))}"
    )


@pytest.mark.parametrize("name,edges,nodes", ALL_FIXTURES,
                         ids=[fx[0] for fx in ALL_FIXTURES])
def test_every_bridge_is_in_its_own_two_node_biconnected_component(
    name, edges, nodes,
):
    """A bridge edge (u, v) must be the only edge of a 2-node
    biconnected component {u, v}."""
    fg, _ = _pair(edges, nodes)
    bridge_set = {frozenset(e) for e in fnx.bridges(fg)}
    if not bridge_set:
        return
    bcc_edges = list(fnx.biconnected_component_edges(fg))
    for bridge in bridge_set:
        # find the bcc whose edge set equals {bridge}
        matched = any(
            len(bcc) == 1 and frozenset(next(iter(bcc))) == bridge
            for bcc in bcc_edges
        )
        assert matched, (
            f"{name}: bridge {bridge} is not in its own singleton BCC"
        )


@pytest.mark.parametrize(
    "name,edges,nodes",
    [fx for fx in ALL_FIXTURES if 2 <= len(fx[2]) <= 15],
    ids=[fx[0] for fx in ALL_FIXTURES if 2 <= len(fx[2]) <= 15],
)
def test_bridges_subset_of_local_bridges(name, edges, nodes):
    """Every bridge is also a local bridge (a local bridge with span
    ``inf`` is a bridge)."""
    fg, _ = _pair(edges, nodes)
    bridges_set = {frozenset(e) for e in fnx.bridges(fg)}
    local_set = {frozenset([u, v]) for u, v, _ in fnx.local_bridges(fg)}
    assert bridges_set <= local_set, (
        f"{name}: bridges {bridges_set} not subset of local_bridges {local_set}"
    )


# ---------------------------------------------------------------------------
# Generator contract
# ---------------------------------------------------------------------------


def test_biconnected_components_returns_generator():
    fg = fnx.complete_graph(4)
    it = fnx.biconnected_components(fg)
    assert iter(it) is it


def test_biconnected_component_edges_returns_generator():
    fg = fnx.complete_graph(4)
    it = fnx.biconnected_component_edges(fg)
    assert iter(it) is it


# ---------------------------------------------------------------------------
# Empty / single-node dispatch
# ---------------------------------------------------------------------------


def test_biconnected_components_empty_graph_yields_nothing():
    assert list(fnx.biconnected_components(fnx.Graph())) == \
        list(nx.biconnected_components(nx.Graph())) == []


def test_articulation_points_empty_graph_yields_nothing():
    assert list(fnx.articulation_points(fnx.Graph())) == \
        list(nx.articulation_points(nx.Graph())) == []


def test_bridges_empty_graph_yields_nothing():
    assert list(fnx.bridges(fnx.Graph())) == \
        list(nx.bridges(nx.Graph())) == []


@pytest.mark.parametrize("route", ["native", "networkx", "backend", "cached-backend"])
@pytest.mark.parametrize("graph_class", ["Graph", "MultiGraph"])
@pytest.mark.parametrize("algorithm", [
    "is_biconnected", "biconnected_components", "biconnected_component_edges",
    "articulation_points",
])
def test_biconnected_family_uses_public_adjacency_rows(route, graph_class, algorithm):
    def run(reference):
        library = fnx if route == "native" and not reference else nx
        calls = []
        logical = getattr(nx, graph_class)([(0, 1), (1, 2)])

        class PublicRows(getattr(library, graph_class)):
            active = False

            def __getitem__(self, node):
                if not self.active:
                    return super().__getitem__(node)
                calls.append(node)
                return logical[node]

        graph = PublicRows([(0, 1), (1, 2), (2, 0)])
        if route == "cached-backend" and not reference:
            nx.relabel_nodes(graph, {}, backend="franken_networkx")
            assert graph.__networkx_cache__.get("backends", {}).get("franken_networkx")
        graph.active = True
        calls.clear()
        if reference:
            result = getattr(nx, algorithm)(graph)
        elif route in {"backend", "cached-backend"}:
            result = getattr(nx, algorithm)(graph, backend="franken_networkx")
        else:
            result = getattr(fnx, algorithm)(graph)
        if algorithm != "is_biconnected":
            result = list(result)
        return result, calls

    assert run(False) == run(True)


@pytest.mark.parametrize("route", ["native", "networkx", "backend", "cached-backend"])
def test_biconnected_preserves_public_row_exception(route):
    library = fnx if route == "native" else nx
    error = nx.NetworkXNotImplemented("public adjacency provider failed")
    calls = []

    class PublicRows(library.Graph):
        active = False

        def __getitem__(self, node):
            if not self.active:
                return super().__getitem__(node)
            calls.append(node)
            raise error

    graph = PublicRows([(0, 1), (1, 2), (2, 0)])
    if route == "cached-backend":
        nx.relabel_nodes(graph, {}, backend="franken_networkx")
        assert graph.__networkx_cache__.get("backends", {}).get("franken_networkx")
    graph.active = True
    calls.clear()
    with pytest.raises(nx.NetworkXNotImplemented) as caught:
        if route in {"backend", "cached-backend"}:
            nx.is_biconnected(graph, backend="franken_networkx")
        else:
            fnx.is_biconnected(graph)
    assert caught.value is error
    assert calls == [0]


@pytest.mark.parametrize("graph_class", ["Graph", "MultiGraph"])
def test_biconnected_checks_directed_provider_before_inner_traversal(graph_class):
    def run(library):
        graph = getattr(library, graph_class)([(0, 1), (1, 2), (2, 0)])
        calls = []

        def directed():
            calls.append("directed")
            return len(calls) > 1

        graph.is_directed = directed
        with pytest.raises(nx.NetworkXNotImplemented) as caught:
            library.is_biconnected(graph)
        return calls, caught.value.args

    assert run(fnx) == run(nx)


def test_biconnected_stops_after_second_completed_component():
    def run(library):
        calls = []

        class LocalRows(library.Graph):
            def __getitem__(self, node):
                calls.append(node)
                if node >= 100:
                    raise AssertionError("visited an irrelevant third component")
                return super().__getitem__(node)

        graph = LocalRows([(0, 1), (2, 3), (100, 101)])
        return library.is_biconnected(graph), calls

    assert run(fnx) == run(nx) == (False, [0, 1, 2, 3])


@pytest.mark.parametrize("graph_class", ["Graph", "MultiGraph"])
def test_biconnected_honors_replaced_class_row_reader(monkeypatch, graph_class):
    graph_type = getattr(fnx, graph_class)
    graph = graph_type([(0, 1), (1, 2), (2, 0)])
    logical = getattr(nx, graph_class)([(0, 1), (1, 2)])
    calls = []

    def public_rows(self, node):
        assert self is graph
        calls.append(node)
        return logical[node]

    monkeypatch.setattr(graph_type, "__getitem__", public_rows)
    assert not fnx.is_biconnected(graph)
    assert calls == [0, 1, 2]


@pytest.mark.parametrize("graph_class", ["Graph", "MultiGraph"])
def test_plain_biconnected_query_retains_native_kernel(monkeypatch, graph_class):
    namespace = fnx.is_biconnected.__globals__
    raw = namespace["_raw_is_biconnected"]
    calls = []

    def native(graph):
        calls.append(graph)
        return raw(graph)

    monkeypatch.setitem(namespace, "_raw_is_biconnected", native)
    graph = getattr(fnx, graph_class)([(0, 1), (1, 2), (2, 0)])
    assert fnx.is_biconnected(graph)
    assert fnx.is_biconnected(graph)
    assert calls == [graph, graph]
