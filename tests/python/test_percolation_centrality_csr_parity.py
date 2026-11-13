"""Parity for the integer-CSR fast path of percolation_centrality.

br-perccsr: for the unweighted case, percolation_centrality replaced the
per-source pure-Python Brandes BFS (string-keyed dicts over fnx adjacency) with
an integer-CSR BFS over flat arrays + a local adjacency list. Brandes
accumulation is order-independent and neighbor order is preserved from G[node],
so the result is bit-identical to the previous dict implementation and matches
networkx within float tolerance. 173ms -> 33ms (faster than nx).
"""

import random
from decimal import Decimal
from fractions import Fraction

import networkx as nx
import pytest

import franken_networkx as fnx


def _mk(n, seed, *, directed=False, attr=True):
    if directed:
        base = nx.gnm_random_graph(n, min(n * 5, n * (n - 1)), seed=seed, directed=True)
    elif n > 4:
        k = 6 if (n - 1) >= 6 else (n - 1 if (n - 1) % 2 == 0 else n - 2)
        base = nx.connected_watts_strogatz_graph(n, k, 0.3, seed=seed)
    else:
        base = nx.path_graph(n)
    rnd = random.Random(seed)
    if attr:
        for node in base.nodes():
            base.nodes[node]["percolation"] = round(rnd.random(), 3)
    Gf = (fnx.DiGraph if directed else fnx.Graph)()
    Gf.add_nodes_from((node, dict(d)) for node, d in base.nodes(data=True))
    Gf.add_edges_from(base.edges())
    return base, Gf


def _close(a, b, tol=1e-12):
    return set(a) == set(b) and all(abs(a[k] - b[k]) <= tol for k in a)


def test_parity_matrix():
    for n, directed, attr in [
        (80, False, True),
        (60, True, True),
        (100, False, False),
        (50, True, False),
        (3, False, True),
        (5, False, True),
    ]:
        Gx, Gf = _mk(n, n + int(directed), directed=directed, attr=attr)
        assert _close(
            nx.percolation_centrality(Gx), fnx.percolation_centrality(Gf)
        ), (n, directed, attr)


def test_custom_states_dict():
    Gx, Gf = _mk(40, 7, attr=False)
    rnd = random.Random(9)
    states = {i: rnd.random() for i in Gx.nodes()}
    assert _close(
        nx.percolation_centrality(Gx, states=states),
        fnx.percolation_centrality(Gf, states=states),
    )


def test_default_attribute_is_one():
    # No 'percolation' attribute set -> every node defaults to state 1.
    Gx, Gf = _mk(60, 3, attr=False)
    assert _close(
        nx.percolation_centrality(Gx), fnx.percolation_centrality(Gf)
    )


def test_directed_graph_uses_successors():
    Gx, Gf = _mk(70, 11, directed=True)
    assert _close(
        nx.percolation_centrality(Gx), fnx.percolation_centrality(Gf)
    )


def test_weighted_path_still_supported():
    # weight != None falls through to the existing Dijkstra-basic path.
    base = nx.connected_watts_strogatz_graph(40, 6, 0.3, seed=5)
    rnd = random.Random(5)
    for u, v in base.edges():
        base[u][v]["weight"] = rnd.randint(1, 9)
    for node in base.nodes():
        base.nodes[node]["percolation"] = round(rnd.random(), 3)
    Gf = fnx.Graph()
    Gf.add_nodes_from((n, dict(d)) for n, d in base.nodes(data=True))
    Gf.add_edges_from((u, v, dict(d)) for u, v, d in base.edges(data=True))
    assert _close(
        nx.percolation_centrality(base, weight="weight"),
        fnx.percolation_centrality(Gf, weight="weight"),
    )


def _state_graph(library, cls_name):
    graph = getattr(library, cls_name)()
    graph.add_nodes_from(range(4))
    graph.add_weighted_edges_from([(0, 1, 1), (1, 2, 2), (2, 3, 1), (0, 3, 7)])
    if graph.is_multigraph():
        graph.add_edge(0, 1, weight=3)
    return graph


@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("library", [nx, fnx], ids=["networkx-input", "native-input"])
@pytest.mark.parametrize("weight", [None, "weight"])
def test_percolation_accepts_ordinary_graph_inputs(cls_name, library, weight):
    graph = _state_graph(library, cls_name)
    expected = nx.percolation_centrality(_state_graph(nx, cls_name), weight=weight)
    assert fnx.percolation_centrality(graph, weight=weight) == pytest.approx(expected)


@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("library", [nx, fnx], ids=["networkx-input", "native-input"])
@pytest.mark.parametrize("weight", [None, "weight"])
@pytest.mark.parametrize("state_kind", ["outside", "reordered", "fraction"])
def test_percolation_preserves_supplied_state_domain(cls_name, library, weight, state_kind):
    if state_kind == "outside":
        states = {0: 0.25, 1: 0.5, 2: 0.75, 3: 1.0, "outside": 5.0}
    elif state_kind == "reordered":
        # The mapping fold is 3.0, while a graph-ordered fold is 2.0.
        states = {0: 1e16, 2: -1e16, 1: 1.0, 3: 2.0}
    else:
        states = {node: Fraction(1, node + 3) for node in range(4)}
    expected = nx.percolation_centrality(
        _state_graph(nx, cls_name), states=states, weight=weight
    )
    actual = fnx.percolation_centrality(
        _state_graph(library, cls_name), states=states, weight=weight
    )
    assert actual == expected


@pytest.mark.parametrize("library", [nx, fnx], ids=["networkx-input", "native-input"])
@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph"])
@pytest.mark.parametrize("weight", [None, "weight"])
@pytest.mark.parametrize("kind", ["zero", "decimal", "missing"])
def test_percolation_keeps_state_errors(library, cls_name, weight, kind):
    states = {
        "zero": dict.fromkeys(range(4), 0.0),
        "decimal": dict.fromkeys(range(4), Decimal("0.5")),
        "missing": {0: 0.5, 1: 0.5, 3: 0.5},
    }[kind]
    with pytest.raises((ZeroDivisionError, TypeError, KeyError)) as oracle:
        nx.percolation_centrality(_state_graph(nx, cls_name), states=states, weight=weight)
    with pytest.raises(type(oracle.value)) as actual:
        fnx.percolation_centrality(_state_graph(library, cls_name), states=states, weight=weight)
    assert str(actual.value) == str(oracle.value)


@pytest.mark.parametrize("library", [nx, fnx], ids=["networkx-input", "native-input"])
def test_percolation_zero_states_on_isolates_do_not_divide(library):
    graph = library.Graph()
    graph.add_nodes_from(range(3))
    assert fnx.percolation_centrality(graph, states=dict.fromkeys(graph, 0.0)) == {
        0: 0.0, 1: 0.0, 2: 0.0
    }


@pytest.mark.parametrize("library", [nx, fnx], ids=["networkx-input", "native-input"])
@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph"])
def test_unweighted_percolation_ignores_internal_name_collision(library, cls_name):
    graph = getattr(library, cls_name)()
    graph.add_edges_from([(0, 1), (1, 2), (0, 2)])
    graph[0][2]["\x00__fnx_unit_weight_sentinel__"] = 20
    expected = nx.percolation_centrality(nx.DiGraph(graph) if graph.is_directed() else nx.Graph(graph))
    assert fnx.percolation_centrality(graph) == expected


class _ChangingStates(dict):
    def __init__(self, graph):
        super().__init__(dict.fromkeys(graph, 0.5))
        self.graph = graph
        self.reads = []

    def values(self):
        self.reads.append("values")
        return super().values()

    def __getitem__(self, node):
        self.reads.append(node)
        if len(self.reads) == 2:
            self.graph.add_edge(1, 3, weight=1)
        return super().__getitem__(node)


@pytest.mark.parametrize("library", [nx, fnx], ids=["networkx-input", "native-input"])
@pytest.mark.parametrize("weight", [None, "weight"])
def test_percolation_state_reads_can_change_later_sources(library, weight):
    graph = _state_graph(library, "DiGraph")
    reference = _state_graph(nx, "DiGraph")
    states, oracle_states = _ChangingStates(graph), _ChangingStates(reference)
    expected = nx.percolation_centrality(reference, states=oracle_states, weight=weight)
    assert fnx.percolation_centrality(graph, states=states, weight=weight) == expected
    assert states.reads == oracle_states.reads
    assert graph.has_edge(1, 3)
