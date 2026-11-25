"""Parity for the native (delegation-free) voronoi_cells.

br-voronoinative: `voronoi_cells` previously delegated to networkx (the Rust
`voronoi_cells_rust` ignored `weight` and mis-assigned centers). It is now
rebuilt on fnx's own `multi_source_dijkstra_path` + the standard
nearest-center inversion, dropping the `_fnx_to_nx` conversion. These tests
pin it bit-identical to nx across the parameter matrix.
"""

import random

import networkx as nx
import pytest

import franken_networkx as fnx


def _mk(*, directed=False, weighted=True, seed=3, disconnected=False, n=80):
    Gx = nx.connected_watts_strogatz_graph(n, 4, 0.3, seed=seed)
    if directed:
        Gx = Gx.to_directed()
    rnd = random.Random(seed)
    if weighted:
        for u, v in Gx.edges():
            Gx[u][v]["weight"] = rnd.randint(1, 10)
    if disconnected:
        Gx.add_nodes_from([900, 901, 902])
    Gf = (fnx.DiGraph if directed else fnx.Graph)()
    Gf.add_nodes_from(Gx.nodes())
    for u, v, d in Gx.edges(data=True):
        Gf.add_edge(u, v, **({"weight": d["weight"]} if weighted else {}))
    return Gx, Gf


def _eq(vx, vf):
    return vx == vf and list(vx) == list(vf)


def test_parameter_matrix_parity():
    for directed in (False, True):
        for weighted in (True, False):
            for disconnected in (False, True):
                Gx, Gf = _mk(
                    directed=directed, weighted=weighted, disconnected=disconnected
                )
                w = "weight" if weighted else None
                assert _eq(
                    nx.voronoi_cells(Gx, {0, 40}, weight=w),
                    fnx.voronoi_cells(Gf, {0, 40}, weight=w),
                ), (directed, weighted, disconnected)


def test_single_center():
    Gx, Gf = _mk(seed=5)
    assert _eq(
        nx.voronoi_cells(Gx, {0}, weight="weight"),
        fnx.voronoi_cells(Gf, {0}, weight="weight"),
    )


def test_unreachable_nodes_grouped():
    Gx, Gf = _mk(disconnected=True)
    vf = fnx.voronoi_cells(Gf, {0, 40}, weight="weight")
    assert "unreachable" in vf
    assert {900, 901, 902} <= vf["unreachable"]
    assert vf == nx.voronoi_cells(Gx, {0, 40}, weight="weight")


def test_empty_centers_raises_valueerror():
    _, Gf = _mk()
    try:
        fnx.voronoi_cells(Gf, [], weight="weight")
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected ValueError for empty center_nodes")


def test_bad_center_raises_node_not_found():
    Gx, Gf = _mk()
    nx_exc = fnx_exc = None
    try:
        nx.voronoi_cells(Gx, {99999}, weight="weight")
    except Exception as e:  # noqa: BLE001
        nx_exc = type(e).__name__
    try:
        fnx.voronoi_cells(Gf, {99999}, weight="weight")
    except Exception as e:  # noqa: BLE001
        fnx_exc = type(e).__name__
    assert nx_exc == fnx_exc == "NodeNotFound"


def test_weighted_tie_break_matches_nx():
    # 4-cycle 0-1-2-3-0 with a heavier 0-2 shortcut; node 3 is closer to 2.
    Gx = nx.Graph()
    Gf = fnx.Graph()
    for u, v, w in [(0, 1, 1), (1, 2, 1), (2, 3, 1), (3, 0, 1), (0, 2, 2)]:
        Gx.add_edge(u, v, weight=w)
        Gf.add_edge(u, v, weight=w)
    assert _eq(
        nx.voronoi_cells(Gx, {0, 2}, weight="weight"),
        fnx.voronoi_cells(Gf, {0, 2}, weight="weight"),
    )


def _collision_twins(cls_name, scale, seed, weighted):
    # Three BA pieces, scattered edges and isolated nodes, labels scaled so
    # hashes collide (x1024 lands every label in slot 0 of any table under 1024).
    r = random.Random(seed)
    edges, off = [], 0
    for size in (50, 30, 20):
        for a, b in nx.barabasi_albert_graph(size, 2, seed=seed + size).edges():
            edges.append((scale * (a + off), scale * (b + off)))
        off += size
    edges += [(scale * r.randrange(120), scale * r.randrange(120)) for _ in range(10)]
    r.shuffle(edges)
    nodes = [scale * x for x in r.sample(range(130), 130)]
    Gx, Gf = getattr(nx, cls_name)(), getattr(fnx, cls_name)()
    for g in (Gx, Gf):
        g.add_nodes_from(nodes)
        for u, v in edges:
            if weighted:
                g.add_edge(u, v, weight=(u + 3 * v) % 5 + 1)
            else:
                g.add_edge(u, v)
    return Gx, Gf


@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph", "MultiGraph"])
@pytest.mark.parametrize("weighted", [False, True])
@pytest.mark.parametrize("scale", [1, 37, 1024])
@pytest.mark.parametrize("seed", range(3))
def test_each_cell_iterates_in_networkx_order(cls_name, weighted, scale, seed):
    # br-r37-c1-ygt3z: each cell is a set networkx grows in its paths dict's
    # (settle) order; list() of it is observable, and a kernel settling equal
    # distances in another order put 12 of 36 graphs' cells in another order.
    Gx, Gf = _collision_twins(cls_name, scale, seed, weighted)
    centers = list(Gx)[:4]
    want = nx.voronoi_cells(Gx, centers, weight="weight")
    got = fnx.voronoi_cells(Gf, centers, weight="weight")
    assert [(k, list(v)) for k, v in got.items()] == [(k, list(v)) for k, v in want.items()]


_LIVE_VORONOI_ROUTES = (
    "fnx-input", "nx-input", "module", "algorithms", "backend", "cached-backend"
)


def _call_live_voronoi(route, graph, centers, weight, *, reference=False):
    if reference:
        return nx.voronoi_cells(graph, centers, weight=weight, backend="networkx")
    if route in {"backend", "cached-backend"}:
        return nx.voronoi_cells(graph, centers, weight=weight, backend="franken_networkx")
    if route == "module":
        from franken_networkx import voronoi

        return voronoi.voronoi_cells(graph, centers, weight=weight)
    if route == "algorithms":
        return fnx.algorithms.voronoi_cells(graph, centers, weight=weight)
    return fnx.voronoi_cells(graph, centers, weight=weight)


def _prewarm_voronoi_input(route, graph, reference):
    if route == "cached-backend" and not reference:
        # The relabel backend produces a conversion containing all attributes,
        # so NetworkX can reuse it for the later weighted query.
        nx.relabel_nodes(graph, {}, backend="franken_networkx")
        assert graph.__networkx_cache__.get("backends", {}).get("franken_networkx")


@pytest.mark.parametrize("route", _LIVE_VORONOI_ROUTES)
@pytest.mark.parametrize("graph_class", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("filtered", [False, True])
def test_voronoi_weight_callbacks_keep_original_rows_and_mutations(
    route, graph_class, filtered
):
    def run(reference):
        library = fnx if route == "fnx-input" and not reference else nx
        root = getattr(library, graph_class)()
        root.add_nodes_from([0, 4, 1, 2, 3, 5])
        root.add_weighted_edges_from([
            (0, 1, 1), (1, 2, 9), (4, 2, 4), (4, 3, 1), (0, 2, 10)
        ])
        root.add_edge(4, 5, weight=0, hidden=True)
        if root.is_multigraph():
            root.add_edge(0, 1, key="parallel", weight=3)
        if filtered:
            root.add_weighted_edges_from([(0, 9, 0), (9, 2, 0)])
            graph = library.subgraph_view(root, filter_node=lambda node: node != 9)
        else:
            graph = root
        _prewarm_voronoi_input(route, graph, reference)
        calls = []
        changed = False

        def weight(u, v, data):
            nonlocal changed
            calls.append((u, v))
            if graph.is_multigraph():
                for key, attrs in data.items():
                    assert attrs is graph[u][v][key]
                attributes = list(data.values())
            else:
                assert data is graph[u][v]
                attributes = [data]
            for attrs in attributes:
                attrs["visited"] = True
            if (u, v) == (0, 1) and not changed:
                changed = True
                later = root[1][2][0] if root.is_multigraph() else root[1][2]
                later["weight"] = 1
                root.add_edge(1, 6, weight=1)
            visible = [attrs["weight"] for attrs in attributes if not attrs.get("hidden")]
            return min(visible) if visible else None

        cells = _call_live_voronoi(route, graph, [0, 4], weight, reference=reference)
        assert changed
        assert 6 in cells[0]
        assert 5 in cells["unreachable"]
        edge_options = {"keys": True} if root.is_multigraph() else {}
        return (
            [(center, list(cell)) for center, cell in cells.items()],
            calls,
            list(root.edges(data=True, **edge_options)),
        )

    assert run(False) == run(True)


@pytest.mark.parametrize("route", ["backend", "cached-backend"])
@pytest.mark.parametrize("graph_class", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("mutation", ["topology", "attributes"])
def test_voronoi_backend_consumes_centers_before_snapshotting(route, graph_class, mutation):
    def run(reference):
        graph = getattr(nx, graph_class)()
        graph.add_weighted_edges_from([(0, 1, 10), (1, 2, 1), (3, 2, 1)])
        _prewarm_voronoi_input(route, graph, reference)

        class Centers(list):
            changed = False

            def __iter__(self):
                if not self.changed:
                    self.changed = True
                    if mutation == "topology":
                        graph.add_edge(0, 2, weight=1)
                    else:
                        attrs = graph[0][1][0] if graph.is_multigraph() else graph[0][1]
                        attrs["weight"] = 1
                return super().__iter__()

        centers = Centers([0, 3])
        cells = _call_live_voronoi(route, graph, centers, "weight", reference=reference)
        assert centers.changed
        if not reference:
            assert not graph.__networkx_cache__.get("backends")
        # An attribute-only write does not call a graph mutator. Reusing the
        # conversion that preceded center selection would return the old cost.
        following = nx.dijkstra_path_length(
            graph, 0, 2, backend="networkx" if reference else "franken_networkx"
        )
        return [(center, list(cell)) for center, cell in cells.items()], following

    assert run(False) == run(True)


@pytest.mark.parametrize("route", _LIVE_VORONOI_ROUTES)
@pytest.mark.parametrize("graph_class", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("weight", ["weight", None])
def test_voronoi_undirected_views_preserve_each_endpoints_weights(route, graph_class, weight):
    def run(reference):
        library = fnx if route == "fnx-input" and not reference else nx
        root = getattr(library, graph_class)()
        for u, v, value in [
            (0, 1, 8), (1, 0, 1), (1, 2, 1), (2, 1, 1), (2, 3, 1), (3, 2, 8)
        ]:
            root.add_edge(u, v)
            attrs = root[u][v][0] if root.is_multigraph() else root[u][v]
            attrs[weight] = value
        graph = root.to_undirected(as_view=True)
        _prewarm_voronoi_input(route, graph, reference)
        cells = _call_live_voronoi(route, graph, [0, 3], weight, reference=reference)
        return [(center, list(cell)) for center, cell in cells.items()]

    assert run(False) == run(True)


@pytest.mark.parametrize("route", ["nx-input", "module", "algorithms", "backend", "cached-backend"])
@pytest.mark.parametrize("graph_class", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_voronoi_custom_center_hash_can_change_later_weights(route, graph_class):
    def run(reference):
        graph = getattr(nx, graph_class)()
        graph.add_weighted_edges_from([(0, 1, 10), (1, 2, 1), (3, 2, 1)])
        _prewarm_voronoi_input(route, graph, reference)
        changed = False

        class Center(int):
            def __hash__(self):
                nonlocal changed
                if not changed:
                    changed = True
                    attrs = graph[0][1][0] if graph.is_multigraph() else graph[0][1]
                    attrs["weight"] = 1
                return int.__hash__(self)

        cells = _call_live_voronoi(
            route, graph, [Center(0), 3], "weight", reference=reference
        )
        assert changed
        return [(int(center), list(cell)) for center, cell in cells.items()]

    assert run(False) == run(True)


@pytest.mark.parametrize("route", ["backend", "cached-backend"])
def test_voronoi_backend_preserves_callback_exception_identity(route):
    graph = nx.path_graph(3)
    _prewarm_voronoi_input(route, graph, False)
    error = fnx.NetworkXNotImplemented("weight provider refused this edge")
    calls = []

    def weight(u, v, attrs):
        calls.append((u, v))
        assert attrs is graph[u][v]
        raise error

    with pytest.raises(fnx.NetworkXNotImplemented) as caught:
        _call_live_voronoi(route, graph, [0], weight)
    assert caught.value is error
    assert calls == [(0, 1)]
