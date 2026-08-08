"""double_edge_swap / connected_double_edge_swap degree-preservation invariants.

The double-edge-swap rewiring functions are randomized (and fnx's RNG diverges
from networkx's, so they cannot be parity-tested), but they have exact defining
invariants:
  - a double edge swap removes two edges and adds two, so it PRESERVES every
    node's degree (hence the whole degree sequence) and the edge count;
  - connected_double_edge_swap additionally PRESERVES connectivity.
These hold for whatever random rewiring is performed.

Preservation invariants alone are all satisfied by a function that does nothing,
so each test also pins that the rewiring actually happened. Degrees are compared
PER NODE rather than as a sorted sequence: swapping two nodes' degrees preserves
the sequence but is not a legal double edge swap.

The rewiring cannot be parity-tested, but the error contracts are not random —
they are compared against networkx directly.

No mocks: real fnx.
"""

from __future__ import annotations

import random

import networkx as nx
import pytest
import franken_networkx as fnx


def _graph(seed):
    r = random.Random(seed)
    n = r.randint(8, 14)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.4]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)
    return g


def _edge_set(g):
    """Undirected edge set, so an edge is not counted twice by orientation."""
    return {frozenset((u, v)) for u, v in g.edges()}


@pytest.mark.parametrize("seed", range(40))
def test_double_edge_swap_preserves_degree_sequence(seed):
    g = _graph(seed)
    if g.number_of_edges() < 2:
        pytest.skip("too few edges to swap")
    deg_before = sorted(d for _, d in g.degree())
    edges_before = g.number_of_edges()

    h = g.copy()
    returned = fnx.double_edge_swap(h, nswap=5, max_tries=200, seed=seed)

    assert sorted(d for _, d in h.degree()) == deg_before   # degree sequence kept
    assert h.number_of_edges() == edges_before               # edge count kept
    # Stronger than the sequence: EVERY node keeps its own degree. Permuting two
    # nodes' degrees would leave the sorted sequence intact but is not a swap.
    assert dict(h.degree()) == dict(g.degree())
    assert set(h.nodes()) == set(g.nodes())                  # swaps rewire, never add/drop nodes
    # ...and the rewiring actually happened, so a no-op cannot pass this test.
    assert _edge_set(h) != _edge_set(g)
    assert returned is h                                     # mutates in place, returns the graph


@pytest.mark.parametrize("seed", range(40))
def test_connected_swap_preserves_degree_and_connectivity(seed):
    g = _graph(seed)
    if g.number_of_edges() < 2 or not fnx.is_connected(g):
        pytest.skip("not connected / too few edges")
    deg_before = sorted(d for _, d in g.degree())
    edges_before = g.number_of_edges()

    h = g.copy()
    swaps = fnx.connected_double_edge_swap(h, nswap=5, seed=seed)

    assert sorted(d for _, d in h.degree()) == deg_before
    assert h.number_of_edges() == edges_before
    assert fnx.is_connected(h)                                # connectivity kept
    assert dict(h.degree()) == dict(g.degree())               # per node, not just the sequence
    assert set(h.nodes()) == set(g.nodes())
    assert _edge_set(h) != _edge_set(g)                       # not a no-op
    # Returns the number of successful swaps, which cannot exceed the request.
    assert isinstance(swaps, int) and 0 < swaps <= 5


def test_swap_keeps_no_self_loops_or_multi_edges():
    # A simple graph stays simple after swaps (no self-loops, no parallel edges).
    g = fnx.gnm_random_graph(12, 24, seed=3)
    h = g.copy()
    fnx.double_edge_swap(h, nswap=10, max_tries=500, seed=3)
    assert fnx.number_of_selfloops(h) == 0
    assert h.number_of_edges() == g.number_of_edges()
    # `not h.is_multigraph()` only restated h's class. What actually has to hold
    # is that no swap collapsed two edges onto one pair: the reported edge count
    # and the distinct undirected pairs must still agree.
    listed = list(h.edges())
    assert len(listed) == len(_edge_set(h)) == g.number_of_edges()
    assert all(u != v for u, v in listed)


# --- error contracts: deterministic, so these ARE comparable against networkx ---

def _raises(fn):
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 - the type is the assertion
        return type(exc).__name__, str(exc)
    return None, None


@pytest.mark.parametrize(
    "build, call",
    [
        ("path_graph_3", lambda lib, g: lib.double_edge_swap(g, nswap=1, max_tries=10)),
        ("gnm_10_20", lambda lib, g: lib.double_edge_swap(g, nswap=10, max_tries=2)),
        ("digraph_c4", lambda lib, g: lib.double_edge_swap(g, nswap=1, max_tries=10)),
        ("disconnected", lambda lib, g: lib.connected_double_edge_swap(g, nswap=1)),
        ("path_graph_3", lambda lib, g: lib.connected_double_edge_swap(g, nswap=1)),
    ],
    ids=["too_few_nodes", "nswap_over_max_tries", "directed", "cdes_disconnected", "cdes_too_few_nodes"],
)
def test_error_contracts_match_networkx(build, call):
    def make(lib):
        if build == "path_graph_3":
            return lib.path_graph(3)
        if build == "gnm_10_20":
            return lib.gnm_random_graph(10, 20, seed=1)
        if build == "digraph_c4":
            return lib.DiGraph([(0, 1), (1, 2), (2, 3), (3, 0)])
        return lib.Graph([(0, 1), (2, 3), (4, 5), (6, 7)])

    nx_type, nx_msg = _raises(lambda: call(nx, make(nx)))
    fnx_type, fnx_msg = _raises(lambda: call(fnx, make(fnx)))

    assert nx_type is not None, "networkx no longer raises here — retune the case"
    assert (fnx_type, fnx_msg) == (nx_type, nx_msg)
