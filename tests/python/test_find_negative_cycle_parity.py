"""Parity coverage for find_negative_cycle.

Bead franken_networkx-94ld: the Rust implementation rejected directed
graphs with NetworkXNotImplemented; the Python wrapper routed directed
inputs through networkx's algorithm so both the success path and the
missing-source / no-cycle error contracts match upstream exactly.

nro4w.7: undirected graphs stayed on the native kernel, which returned a
valid negative cycle but not networkx's in 189 of 400 random graphs and
panicked (index usize::MAX) on a lone negative edge. Every graph now runs
networkx's detector in-process.
"""

import random

import networkx as nx
import pytest

import franken_networkx as fnx


def test_find_negative_cycle_directed_graph_matches_networkx():
    edges = [(0, 1, 1), (1, 2, -3), (2, 0, 1)]
    fg = fnx.DiGraph()
    fg.add_weighted_edges_from(edges)
    ng = nx.DiGraph()
    ng.add_weighted_edges_from(edges)

    f_cycle = fnx.find_negative_cycle(fg, 0)
    n_cycle = nx.find_negative_cycle(ng, 0)
    # Node list parity.
    assert f_cycle == n_cycle


def test_find_negative_cycle_directed_missing_source_matches_networkx():
    fg = fnx.DiGraph()
    fg.add_weighted_edges_from([(0, 1, -1), (1, 0, -1)])
    ng = nx.DiGraph()
    ng.add_weighted_edges_from([(0, 1, -1), (1, 0, -1)])

    with pytest.raises((fnx.NodeNotFound, nx.NodeNotFound), match="Source 99 not in G"):
        fnx.find_negative_cycle(fg, 99)
    with pytest.raises(nx.NodeNotFound, match="Source 99 not in G"):
        nx.find_negative_cycle(ng, 99)


def test_find_negative_cycle_directed_no_cycle_raises_networkx_error():
    fg = fnx.DiGraph()
    fg.add_weighted_edges_from([(0, 1, 1), (1, 2, 1)])
    ng = nx.DiGraph()
    ng.add_weighted_edges_from([(0, 1, 1), (1, 2, 1)])

    with pytest.raises(
        (fnx.NetworkXError, nx.NetworkXError), match="No negative cycles detected"
    ):
        fnx.find_negative_cycle(fg, 0)
    with pytest.raises(nx.NetworkXError, match="No negative cycles detected"):
        nx.find_negative_cycle(ng, 0)


@pytest.mark.parametrize("source", [0, 1])
def test_lone_negative_undirected_edge_matches_networkx(source):
    # networkx's own test_find_negative_cycle_single_edge; the native kernel
    # panicked here.
    G = fnx.Graph()
    G.add_edge(0, 1, weight=-1)
    H = nx.Graph()
    H.add_edge(0, 1, weight=-1)
    assert fnx.find_negative_cycle(G, source) == nx.find_negative_cycle(H, source)


def _outcome(module, cls_name, n, edges, source):
    G = getattr(module, cls_name)()
    G.add_nodes_from(range(n))
    G.add_weighted_edges_from(edges)
    try:
        return module.find_negative_cycle(G, source)
    except Exception as exc:  # the error contract is part of the parity
        return type(exc).__name__, str(exc)


@pytest.mark.parametrize("cls_name", ["Graph", "MultiGraph", "DiGraph", "MultiDiGraph"])
def test_random_graphs_return_networkx_cycle(cls_name):
    rng = random.Random(9)
    compared = 0
    for _ in range(300):
        n = rng.randint(2, 7)
        edges = [
            (rng.randrange(n), rng.randrange(n), rng.choice([-3, -1, 1, 2, 5]))
            for _ in range(rng.randint(1, 10))
        ]
        source = edges[0][0]
        expected = _outcome(nx, cls_name, n, edges, source)
        if expected[0] == "AttributeError":
            # Owned divergence: when the detected node carries a self-loop,
            # networkx evaluates ``weight(G, v, v)`` (graph passed as the
            # edge's ``u``) and crashes on ``int.get``. fnx evaluates the
            # self-loop's weight as networkx intends.
            continue
        compared += 1
        assert _outcome(fnx, cls_name, n, edges, source) == expected, (edges, source)
    assert compared > 250


def test_weights_written_after_construction_are_seen():
    # The scenario test_edge_attr_native_store_flush pinned on the removed
    # native binding: weights set through G[u][v] after add_edges_from.
    weights = {("a", "b"): -5.0, ("b", "c"): 1.0, ("a", "c"): 1.0}
    G = fnx.Graph()
    G.add_edges_from(list(weights))
    H = nx.Graph()
    H.add_edges_from(list(weights))
    for (u, v), w in weights.items():
        G[u][v]["weight"] = w
        H[u][v]["weight"] = w
    assert fnx.find_negative_cycle(G, "a") == nx.find_negative_cycle(H, "a")
