"""Tests for A* shortest path and Yen's K-shortest simple paths."""

import re
from decimal import Decimal
from fractions import Fraction

import networkx as nx
import pytest

import franken_networkx as fnx


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def weighted_triangle():
    """Triangle with unequal weights: direct 0->2 is expensive."""
    G = fnx.Graph()
    G.add_edge(0, 1, weight=1.0)
    G.add_edge(1, 2, weight=1.0)
    G.add_edge(0, 2, weight=5.0)
    return G


@pytest.fixture
def diamond():
    """Diamond: 0--1--3, 0--2--3, with weights."""
    G = fnx.Graph()
    G.add_edge(0, 1, weight=1.0)
    G.add_edge(0, 2, weight=2.0)
    G.add_edge(1, 3, weight=1.0)
    G.add_edge(2, 3, weight=1.0)
    return G


@pytest.fixture
def path5():
    G = fnx.Graph()
    for i in range(4):
        G.add_edge(i, i + 1, weight=1.0)
    return G


# ---------------------------------------------------------------------------
# astar_path
# ---------------------------------------------------------------------------


class TestAstarPath:
    def test_basic(self, weighted_triangle):
        path = fnx.astar_path(weighted_triangle, 0, 2)
        assert path == [0, 1, 2]

    def test_same_node(self):
        G = fnx.Graph()
        G.add_node(0)
        path = fnx.astar_path(G, 0, 0)
        assert path == [0]

    def test_no_path_raises(self):
        G = fnx.Graph()
        G.add_node(0)
        G.add_node(1)
        # br-astarnop: fnx now raises NetworkXNoPath matching nx.
        with pytest.raises(fnx.NetworkXNoPath):
            fnx.astar_path(G, 0, 1)

    def test_with_zero_heuristic(self, weighted_triangle):
        path = fnx.astar_path(weighted_triangle, 0, 2, heuristic=lambda u, v: 0)
        assert path == [0, 1, 2]

    def test_diamond(self, diamond):
        path = fnx.astar_path(diamond, 0, 3)
        # 0->1->3 has total weight 2, 0->2->3 has total weight 3.
        assert path == [0, 1, 3]

    def test_path5(self, path5):
        path = fnx.astar_path(path5, 0, 4)
        assert path == [0, 1, 2, 3, 4]

    def test_string_nodes(self):
        G = fnx.Graph()
        G.add_edge("a", "b", weight=1.0)
        G.add_edge("b", "c", weight=1.0)
        path = fnx.astar_path(G, "a", "c")
        assert path == ["a", "b", "c"]

    def test_heuristic_exception_matches_networkx(self):
        G_fnx = fnx.path_graph(3)
        G_nx = nx.path_graph(3)

        def heuristic(u, v):
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError) as expected:
            nx.astar_path(G_nx, 0, 2, heuristic=heuristic)

        with pytest.raises(type(expected.value), match=re.escape(str(expected.value))):
            fnx.astar_path(G_fnx, 0, 2, heuristic=heuristic)

    def test_callable_weight_matches_networkx(self):
        G_fnx = fnx.Graph()
        G_nx = nx.Graph()
        for graph in (G_fnx, G_nx):
            graph.add_edge("a", "b", length=2, penalty=0)
            graph.add_edge("a", "c", length=5, penalty=0)
            graph.add_edge("b", "c", length=1, penalty=0)
            graph.add_edge("b", "d", length=5, penalty=0)
            graph.add_edge("c", "d", length=1, penalty=0)

        def heuristic(u, v):
            return 0

        def weight_fn(u, v, data):
            return data["length"] + data.get("penalty", 0)

        assert fnx.astar_path(
            G_fnx, "a", "d", heuristic=heuristic, weight=weight_fn
        ) == nx.astar_path(
            G_nx, "a", "d", heuristic=heuristic, weight=weight_fn
        )

    def test_cutoff_matches_networkx(self):
        G_fnx = fnx.Graph()
        G_nx = nx.Graph()
        for graph in (G_fnx, G_nx):
            graph.add_edge("a", "b", weight=1.0)
            graph.add_edge("b", "c", weight=1.0)
            graph.add_edge("c", "d", weight=1.0)
            graph.add_edge("a", "d", weight=10.0)

        heuristic = lambda u, v: 0

        assert fnx.astar_path(
            G_fnx, "a", "d", heuristic=heuristic, weight="weight", cutoff=3
        ) == nx.astar_path(
            G_nx, "a", "d", heuristic=heuristic, weight="weight", cutoff=3
        )

        with pytest.raises(nx.NetworkXNoPath) as expected:
            nx.astar_path(
                G_nx, "a", "d", heuristic=heuristic, weight="weight", cutoff=2
            )

        with pytest.raises(fnx.NetworkXNoPath, match=re.escape(str(expected.value))):
            fnx.astar_path(
                G_fnx, "a", "d", heuristic=heuristic, weight="weight", cutoff=2
            )


# ---------------------------------------------------------------------------
# astar_path_length
# ---------------------------------------------------------------------------


class TestAstarPathLength:
    def test_basic(self, weighted_triangle):
        length = fnx.astar_path_length(weighted_triangle, 0, 2)
        assert abs(length - 2.0) < 1e-9

    def test_same_node(self):
        G = fnx.Graph()
        G.add_node(0)
        length = fnx.astar_path_length(G, 0, 0)
        assert abs(length - 0.0) < 1e-9

    def test_no_path_raises(self):
        G = fnx.Graph()
        G.add_node(0)
        G.add_node(1)
        # br-astarnop: fnx now raises NetworkXNoPath matching nx.
        with pytest.raises(fnx.NetworkXNoPath):
            fnx.astar_path_length(G, 0, 1)

    def test_diamond(self, diamond):
        length = fnx.astar_path_length(diamond, 0, 3)
        assert abs(length - 2.0) < 1e-9

    def test_unit_weights(self, path5):
        length = fnx.astar_path_length(path5, 0, 4)
        assert abs(length - 4.0) < 1e-9

    def test_heuristic_exception_matches_networkx(self):
        G_fnx = fnx.path_graph(3)
        G_nx = nx.path_graph(3)

        def heuristic(u, v):
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError) as expected:
            nx.astar_path_length(G_nx, 0, 2, heuristic=heuristic)

        with pytest.raises(type(expected.value), match=re.escape(str(expected.value))):
            fnx.astar_path_length(G_fnx, 0, 2, heuristic=heuristic)

    def test_callable_weight_matches_networkx(self):
        G_fnx = fnx.Graph()
        G_nx = nx.Graph()
        for graph in (G_fnx, G_nx):
            graph.add_edge("a", "b", length=2, penalty=0)
            graph.add_edge("a", "c", length=5, penalty=0)
            graph.add_edge("b", "c", length=1, penalty=0)
            graph.add_edge("b", "d", length=5, penalty=0)
            graph.add_edge("c", "d", length=1, penalty=0)

        def heuristic(u, v):
            return 0

        def weight_fn(u, v, data):
            return data["length"] + data.get("penalty", 0)

        assert fnx.astar_path_length(
            G_fnx, "a", "d", heuristic=heuristic, weight=weight_fn
        ) == nx.astar_path_length(
            G_nx, "a", "d", heuristic=heuristic, weight=weight_fn
        )

    def test_cutoff_matches_networkx(self):
        G_fnx = fnx.Graph()
        G_nx = nx.Graph()
        for graph in (G_fnx, G_nx):
            graph.add_edge("a", "b", weight=1.0)
            graph.add_edge("b", "c", weight=1.0)
            graph.add_edge("c", "d", weight=1.0)
            graph.add_edge("a", "d", weight=10.0)

        heuristic = lambda u, v: 0

        assert fnx.astar_path_length(
            G_fnx, "a", "d", heuristic=heuristic, weight="weight", cutoff=3
        ) == nx.astar_path_length(
            G_nx, "a", "d", heuristic=heuristic, weight="weight", cutoff=3
        )

        with pytest.raises(nx.NetworkXNoPath) as expected:
            nx.astar_path_length(
                G_nx, "a", "d", heuristic=heuristic, weight="weight", cutoff=2
            )

        with pytest.raises(fnx.NetworkXNoPath, match=re.escape(str(expected.value))):
            fnx.astar_path_length(
                G_fnx, "a", "d", heuristic=heuristic, weight="weight", cutoff=2
            )


def _astar_callback_graph(module, class_name, view="graph"):
    graph = getattr(module, class_name)()
    edges = [("s", "a", 1), ("a", "t", 1), ("s", "t", 5)]
    if view == "reverse":
        edges = [(v, u, weight) for u, v, weight in edges]
    graph.add_weighted_edges_from(edges)
    if graph.is_multigraph():
        u, v = ("t", "a") if view == "reverse" else ("a", "t")
        graph.add_edge(u, v, weight=7)
    for node in graph:
        graph.nodes[node]["estimate"] = 0
    if view == "subgraph":
        graph.add_edge("s", "hidden", weight=0)
        return graph.subgraph(["s", "a", "t"])
    if view == "reverse":
        return graph.reverse(copy=False)
    return graph


@pytest.mark.parametrize("api", ["astar_path", "astar_path_length"])
@pytest.mark.parametrize("class_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_astar_heuristic_can_read_graph_adjacency(api, class_name):
    outcomes = []
    for module in (nx, fnx):
        graph = _astar_callback_graph(module, class_name)
        calls = []

        def heuristic(node, target):
            # Reading adjacency can materialize Python dictionaries. A native
            # borrow held across this callback used to panic on that read.
            neighbors = tuple(graph[node])
            calls.append((node, target, neighbors))
            return graph.nodes[node]["estimate"]

        result = getattr(module, api)(graph, "s", "t", heuristic=heuristic)
        outcomes.append((result, calls))
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("api", ["astar_path", "astar_path_length"])
@pytest.mark.parametrize("class_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize(
    "estimate",
    [-(2**60), -(10**1000), Fraction(-(2**60), 1), Decimal(-(2**60))],
    ids=["int-priority", "int-beyond-float", "fraction-priority", "decimal-priority"],
)
def test_astar_heuristic_preserves_exact_priority_arithmetic(api, class_name, estimate):
    outcomes = []
    for module in (nx, fnx):
        graph = _astar_callback_graph(module, class_name)
        calls = []

        def heuristic(node, target):
            calls.append((node, target))
            return estimate

        result = getattr(module, api)(graph, "s", "t", heuristic=heuristic)
        outcomes.append((result, calls))
    # Converting these admissible estimates to f64 erases the difference
    # between priorities for length 2 and length 5 (or overflows altogether).
    expected = ["s", "a", "t"] if api == "astar_path" else 2
    assert outcomes[0][0] == expected
    assert outcomes[1] == outcomes[0]


@pytest.mark.parametrize("api", ["astar_path", "astar_path_length"])
@pytest.mark.parametrize("callback", ["heuristic", "weight"])
@pytest.mark.parametrize("input_module", [fnx, nx], ids=["fnx-input", "networkx-input"])
@pytest.mark.parametrize(
    "class_name, view",
    [
        ("Graph", "graph"),
        ("DiGraph", "graph"),
        ("MultiGraph", "graph"),
        ("MultiDiGraph", "graph"),
        ("Graph", "subgraph"),
        ("DiGraph", "subgraph"),
        ("MultiGraph", "subgraph"),
        ("MultiDiGraph", "subgraph"),
        ("DiGraph", "reverse"),
        ("MultiDiGraph", "reverse"),
    ],
)
def test_astar_callbacks_observe_live_input_graph(api, callback, input_module, class_name, view):
    outcomes = []
    for algorithm_module, graph_module in ((nx, nx), (fnx, input_module)):
        graph = _astar_callback_graph(graph_module, class_name, view)
        attrs = graph["a"]["t"][0] if graph.is_multigraph() else graph["a"]["t"]
        calls = []

        def heuristic(node, target):
            calls.append(("heuristic", node, target))
            if node == "a":
                attrs["weight"] = 100
            return 0

        def weight(u, v, data):
            calls.append(("weight", u, v))
            if (u, v) == ("s", "a"):
                attrs["weight"] = 100
            if graph.is_multigraph():
                return min(edge.get("weight", 1) for edge in data.values())
            return data.get("weight", 1)

        kwargs = {callback: heuristic if callback == "heuristic" else weight}
        result = getattr(algorithm_module, api)(graph, "s", "t", **kwargs)
        outcomes.append((result, calls, attrs["weight"]))
    expected = ["s", "t"] if api == "astar_path" else 5
    assert outcomes[0][0] == expected
    assert outcomes[1] == outcomes[0]


# ---------------------------------------------------------------------------
# shortest_simple_paths
# ---------------------------------------------------------------------------


class TestShortestSimplePaths:
    @staticmethod
    def _live_graph(module, class_name, view):
        base = getattr(module, class_name)()
        edges = [("s", "a", 1), ("a", "t", 1), ("s", "b", 3), ("b", "t", 3)]
        if view == "reverse":
            edges = [(v, u, weight) for u, v, weight in edges]
        base.add_weighted_edges_from(edges)
        if view == "subgraph":
            base.add_edge("s", "hidden", weight=0)
            base.add_edge("hidden", "t", weight=0)
            graph = base.subgraph(["s", "a", "b", "t"])
        elif view == "reverse":
            graph = base.reverse(copy=False)
        else:
            graph = base
        return base, graph

    @pytest.mark.parametrize("phase", ["before_first_next", "between_yields"])
    @pytest.mark.parametrize("weight", [None, "weight"])
    @pytest.mark.parametrize("input_module", [fnx, nx], ids=["fnx-input", "networkx-input"])
    @pytest.mark.parametrize(
        "class_name, view",
        [
            ("Graph", "graph"),
            ("DiGraph", "graph"),
            ("Graph", "subgraph"),
            ("DiGraph", "subgraph"),
            ("DiGraph", "reverse"),
        ],
    )
    def test_live_graph_mutations_reach_lazy_search(
        self, phase, weight, input_module, class_name, view
    ):
        outcomes = []
        for algorithm_module, graph_module in ((nx, nx), (fnx, input_module)):
            base, graph = self._live_graph(graph_module, class_name, view)
            paths = algorithm_module.shortest_simple_paths(graph, "s", "t", weight=weight)
            first = next(paths) if phase == "between_yields" else None
            u, v = ("t", "s") if view == "reverse" else ("s", "t")
            base.add_edge(u, v, weight=4)
            remaining = list(paths)
            assert ["s", "t"] in remaining
            outcomes.append((first, remaining))
        assert outcomes[1] == outcomes[0]

    @pytest.mark.parametrize("input_module", [fnx, nx], ids=["fnx-input", "networkx-input"])
    @pytest.mark.parametrize(
        "class_name, view",
        [
            ("Graph", "graph"),
            ("DiGraph", "graph"),
            ("Graph", "subgraph"),
            ("DiGraph", "subgraph"),
            ("DiGraph", "reverse"),
        ],
    )
    def test_weight_callback_receives_live_edge_dicts(self, input_module, class_name, view):
        outcomes = []
        for algorithm_module, graph_module in ((nx, nx), (fnx, input_module)):
            _, graph = self._live_graph(graph_module, class_name, view)
            calls = []

            def weight(u, v, data):
                assert data is graph.get_edge_data(u, v)
                calls.append((u, v))
                if (u, v) == ("s", "a"):
                    graph["a"]["t"]["weight"] = 100
                return data.get("weight", 1)

            paths = algorithm_module.shortest_simple_paths(graph, "s", "t", weight=weight)
            assert calls == [], "Creating the iterator must not invoke its callback"
            first = next(paths)
            outcomes.append((first, calls, graph["a"]["t"]["weight"]))
        assert outcomes[0][0] == ["s", "b", "t"]
        assert outcomes[1] == outcomes[0]

    @pytest.mark.parametrize("class_name", ["Graph", "DiGraph"])
    @pytest.mark.parametrize("input_module", [fnx, nx], ids=["fnx-input", "networkx-input"])
    @pytest.mark.parametrize("change", ["add_target", "remove_target", "remove_source"])
    def test_endpoint_validation_reads_graph_at_first_next(self, class_name, input_module, change):
        outcomes = []
        for algorithm_module, graph_module in ((nx, nx), (fnx, input_module)):
            graph = getattr(graph_module, class_name)()
            graph.add_edge("s", "a")
            if change != "add_target":
                graph.add_edge("a", "t")
            paths = algorithm_module.shortest_simple_paths(graph, "s", "t")
            if change == "add_target":
                graph.add_edge("a", "t")
            else:
                graph.remove_node("t" if change == "remove_target" else "s")
            try:
                outcomes.append(next(paths))
            except (nx.NodeNotFound, fnx.NodeNotFound) as exc:
                outcomes.append((type(exc).__name__, str(exc)))
        assert outcomes[1] == outcomes[0]

    def test_unweighted_order(self, weighted_triangle):
        # Unweighted: direct edge 0->2 (1 hop) < 0->1->2 (2 hops).
        # shortest_simple_paths is a generator (br-r37-c1-682kr); materialise.
        paths = list(fnx.shortest_simple_paths(weighted_triangle, 0, 2))
        assert len(paths) == 2
        assert paths[0] == [0, 2]
        assert paths[1] == [0, 1, 2]

    def test_weighted_order(self, weighted_triangle):
        # Weighted: 0->1->2 (weight 2) < 0->2 (weight 5).
        paths = list(fnx.shortest_simple_paths(weighted_triangle, 0, 2, weight="weight"))
        assert len(paths) == 2
        assert paths[0] == [0, 1, 2]
        assert paths[1] == [0, 2]

    def test_callable_weight_matches_networkx(self):
        def weight(u, v, data):
            return data["cost"]

        G_fnx = fnx.Graph()
        G_nx = nx.Graph()
        for graph in (G_fnx, G_nx):
            graph.add_edge("a", "b", weight=1.0, cost=5.0)
            graph.add_edge("b", "d", weight=1.0, cost=5.0)
            graph.add_edge("a", "c", weight=1.0, cost=1.0)
            graph.add_edge("c", "d", weight=1.0, cost=1.0)
            graph.add_edge("a", "d", weight=10.0, cost=20.0)

        assert list(fnx.shortest_simple_paths(G_fnx, "a", "d", weight=weight)) == list(
            nx.shortest_simple_paths(G_nx, "a", "d", weight=weight)
        )

    def test_rejects_multigraphs_matches_networkx(self):
        def weight(u, v, data):
            return data["weight"]

        for nx_graph_type, fnx_graph_type in (
            (nx.MultiGraph, fnx.MultiGraph),
            (nx.MultiDiGraph, fnx.MultiDiGraph),
        ):
            G_nx = nx_graph_type()
            G_fnx = fnx_graph_type()
            for graph in (G_nx, G_fnx):
                graph.add_edge(0, 1, weight=1.0)
                graph.add_edge(1, 2, weight=1.0)
                graph.add_edge(0, 2, weight=3.0)

            for weight_arg in (None, "weight", weight):
                with pytest.raises(nx.NetworkXNotImplemented) as expected:
                    list(nx.shortest_simple_paths(G_nx, 0, 2, weight=weight_arg))

                with pytest.raises(
                    fnx.NetworkXNotImplemented, match=re.escape(str(expected.value))
                ):
                    list(fnx.shortest_simple_paths(G_fnx, 0, 2, weight=weight_arg))

    def test_diamond(self, diamond):
        paths = list(fnx.shortest_simple_paths(diamond, 0, 3, weight="weight"))
        assert len(paths) == 2
        # 0->1->3 (weight 2) before 0->2->3 (weight 3).
        assert paths[0] == [0, 1, 3]
        assert paths[1] == [0, 2, 3]

    def test_no_path(self):
        G_fnx = fnx.Graph()
        G_nx = nx.Graph()
        for graph in (G_fnx, G_nx):
            graph.add_node(0)
            graph.add_node(1)

        with pytest.raises(nx.NetworkXNoPath) as expected:
            list(nx.shortest_simple_paths(G_nx, 0, 1))
        with pytest.raises(fnx.NetworkXNoPath, match=re.escape(str(expected.value))):
            list(fnx.shortest_simple_paths(G_fnx, 0, 1))

    def test_same_node(self):
        G = fnx.Graph()
        G.add_node(0)
        paths = list(fnx.shortest_simple_paths(G, 0, 0))
        # Single node path
        assert len(paths) >= 1
        assert paths[0] == [0]

    def test_path5_all_paths(self, path5):
        # In a simple path graph there's only one path from 0 to 4.
        paths = list(fnx.shortest_simple_paths(path5, 0, 4))
        assert len(paths) == 1
        assert paths[0] == [0, 1, 2, 3, 4]

    def test_multiple_paths(self):
        """Graph with multiple alternative paths."""
        G = fnx.Graph()
        G.add_edge(0, 1)
        G.add_edge(0, 2)
        G.add_edge(1, 3)
        G.add_edge(2, 3)
        G.add_edge(1, 2)
        paths = list(fnx.shortest_simple_paths(G, 0, 3))
        # Should find multiple paths of varying lengths.
        assert len(paths) >= 2
        # All paths must start at 0 and end at 3.
        for path in paths:
            assert path[0] == 0
            assert path[-1] == 3
