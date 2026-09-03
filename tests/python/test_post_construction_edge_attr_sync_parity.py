"""br-r37-c1-4tmgq: native kernels must see edge attributes written AFTER construction.

Two attribute stores coexist: the Python edge dicts (what ``G[u][v]`` returns) and the
typed Rust store native kernels read. ``_sync_rust_edge_attrs`` bridges them, but only
when a wrapper calls it. A wrapper that skips it makes the kernel default on miss and
return a plausible WRONG answer while ``G.edges(data=True)`` shows the right values.

Routes: ``B`` writes ``G[u][v][k] = v`` after ``add_edges_from``; ``C`` uses
``set_edge_attributes``. Both are compared against NetworkX on the same graph.

The last test is the planted negative: with the sync monkeypatched to a no-op,
``average_shortest_path_length`` returns the UNWEIGHTED mean, which proves this file
detects a missing sync rather than asserting whatever the code does.
"""

import networkx as nx
import pytest

import franken_networkx as fnx

EDGES = [("s", "m"), ("m", "t"), ("s", "t"), ("m", "x"), ("x", "t"), ("t", "s")]
WEIGHTS = {
    ("s", "m"): 1,
    ("m", "t"): 1,
    ("s", "t"): 5,
    ("m", "x"): 2,
    ("x", "t"): 2,
    ("t", "s"): 3,
}


def build(lib, route, directed):
    G = lib.DiGraph() if directed else lib.Graph()
    G.add_edges_from(EDGES)
    if route == "B":
        for (u, v), w in WEIGHTS.items():
            G[u][v]["weight"] = w
            G[u][v]["partition"] = 0
    elif route == "C":
        lib.set_edge_attributes(
            G, {e: {"weight": w, "partition": 0} for e, w in WEIGHTS.items()}
        )
    else:  # pragma: no cover - guard against a typo in a parametrize list
        raise ValueError(route)
    return G


def tree_edges(T):
    return sorted((str(u), str(v), d.get("weight")) for u, v, d in T.edges(data=True))


@pytest.mark.parametrize("route", ["B", "C"])
@pytest.mark.parametrize("directed", [False, True])
def test_average_shortest_path_length_sees_late_weights(route, directed):
    ref = nx.average_shortest_path_length(build(nx, route, directed), weight="weight")
    got = fnx.average_shortest_path_length(build(fnx, route, directed), weight="weight")
    assert got == pytest.approx(ref)


@pytest.mark.parametrize("route", ["B", "C"])
def test_number_of_spanning_trees_sees_late_weights(route):
    ref = nx.number_of_spanning_trees(build(nx, route, False), weight="weight")
    got = fnx.number_of_spanning_trees(build(fnx, route, False), weight="weight")
    assert got == pytest.approx(ref)


@pytest.mark.parametrize("route", ["B", "C"])
@pytest.mark.parametrize(
    "name", ["minimum_spanning_arborescence", "maximum_spanning_arborescence"]
)
def test_arborescence_sees_late_weights(route, name):
    ref = tree_edges(getattr(nx, name)(build(nx, route, True)))
    got = tree_edges(getattr(fnx, name)(build(fnx, route, True)))
    assert got == ref


@pytest.mark.parametrize("route", ["B", "C"])
def test_partition_spanning_tree_sees_late_weights(route):
    ref = tree_edges(nx.partition_spanning_tree(build(nx, route, False), partition="partition"))
    got = tree_edges(fnx.partition_spanning_tree(build(fnx, route, False), partition="partition"))
    assert got == ref


@pytest.mark.parametrize("route", ["B", "C"])
@pytest.mark.parametrize("directed", [False, True])
def test_all_shortest_paths_sees_late_weights(route, directed):
    ref = sorted(nx.all_shortest_paths(build(nx, route, directed), "s", "t", weight="weight"))
    got = sorted(fnx.all_shortest_paths(build(fnx, route, directed), "s", "t", weight="weight"))
    assert got == ref
    assert got == [["s", "m", "t"]]


def test_missing_sync_is_detected(monkeypatch):
    """Planted negative: the assertions above fail when the sync is skipped."""
    G = build(fnx, "B", False)
    unweighted = fnx.average_shortest_path_length(G)
    ref = nx.average_shortest_path_length(build(nx, "B", False), weight="weight")
    assert unweighted != pytest.approx(ref)

    monkeypatch.setattr(fnx, "_sync_rust_edge_attrs", lambda G, **kwargs: None)
    stale = fnx.average_shortest_path_length(G, weight="weight")
    assert stale == pytest.approx(unweighted)
    assert stale != pytest.approx(ref)
