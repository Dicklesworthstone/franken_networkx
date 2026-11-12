"""Random graph generators: seed-independent structural guarantees.

Random generators are non-deterministic in their edge placement, but each
guarantees an exact structure regardless of seed:
  - gnm_random_graph(n, m): exactly n nodes and m edges;
  - barabasi_albert_graph(n, m): n nodes, m*(n-m) edges, connected;
  - watts_strogatz_graph(n, k, p): n nodes, n*k/2 edges (rewiring keeps count);
  - random_regular_graph(d, n): n nodes all of degree d, d*n/2 edges.
These are oracle-free structural invariants that hold for every seed.

Counting nodes and edges cannot see WHICH nodes and edges: a self-loop still
counts as one edge, a duplicate pair still counts as one, and nothing above
requires the labels to be range(n). Those are pinned below across all four
generators.

Non-determinism also rules out value parity only. A fixed seed reproduces the
graph exactly, p = 0 makes watts_strogatz the ring lattice with no randomness
left in it, and which ARGUMENTS each generator refuses is deterministic — five
such refusals exist and are compared against networkx directly.

No mocks: real fnx.
"""

from __future__ import annotations

import random

import networkx as nx
import pytest
import franken_networkx as fnx


def _raises(fn):
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 - the type IS the assertion
        return type(exc).__name__, str(exc)
    return None, None


def _is_simple_with_range_labels(g):
    listed = list(g.edges())
    return (
        fnx.number_of_selfloops(g) == 0
        and len(listed) == len({frozenset(e) for e in listed})
        and set(g.nodes()) == set(range(g.number_of_nodes()))
    )


@pytest.mark.parametrize("seed", range(30))
def test_gnm_exact_node_and_edge_count(seed):
    r = random.Random(seed)
    n = r.randint(8, 15)
    m = min(r.randint(n - 1, 2 * n), n * (n - 1) // 2)
    g = fnx.gnm_random_graph(n, m, seed=seed)
    assert g.number_of_nodes() == n
    assert g.number_of_edges() == m


@pytest.mark.parametrize("seed", range(30))
def test_barabasi_albert_structure(seed):
    r = random.Random(seed)
    n = r.randint(8, 15)
    m = r.randint(1, 4)
    if n <= m:
        pytest.skip("n must exceed m")
    ba = fnx.barabasi_albert_graph(n, m, seed=seed)
    assert ba.number_of_nodes() == n
    assert ba.number_of_edges() == m * (n - m)   # each of n-m added nodes brings m edges
    assert fnx.is_connected(ba)                   # BA graphs are connected


@pytest.mark.parametrize("seed", range(30))
def test_watts_strogatz_edge_count(seed):
    r = random.Random(seed)
    n = r.randint(8, 15)
    k = 2 * r.randint(1, 3)
    if k >= n:
        pytest.skip("k must be < n")
    ws = fnx.watts_strogatz_graph(n, k, 0.3, seed=seed)
    assert ws.number_of_nodes() == n
    assert ws.number_of_edges() == n * k // 2     # rewiring preserves edge count


@pytest.mark.parametrize("seed", range(30))
def test_random_regular_graph_is_regular(seed):
    r = random.Random(seed)
    n = r.randint(8, 14)
    d = r.randint(2, 4)
    if (d * n) % 2 != 0 or d >= n:
        pytest.skip("d*n must be even and d < n")
    rr = fnx.random_regular_graph(d, n, seed=seed)
    assert all(deg == d for _, deg in rr.degree())
    assert rr.number_of_edges() == d * n // 2


def _all_generators(seed):
    """Every generator the module covers, at parameters valid for this seed."""
    r = random.Random(seed)
    n = r.randint(8, 15)
    m = min(r.randint(n - 1, 2 * n), n * (n - 1) // 2)
    built = [("gnm", fnx.gnm_random_graph(n, m, seed=seed))]

    ba_m = r.randint(1, 4)
    if n > ba_m:
        built.append(("barabasi_albert", fnx.barabasi_albert_graph(n, ba_m, seed=seed)))
    k = 2 * r.randint(1, 3)
    if k < n:
        built.append(("watts_strogatz", fnx.watts_strogatz_graph(n, k, 0.3, seed=seed)))
    d = r.randint(2, 4)
    if (d * n) % 2 == 0 and d < n:
        built.append(("random_regular", fnx.random_regular_graph(d, n, seed=seed)))
    return built


@pytest.mark.parametrize("seed", range(30))
def test_generated_graphs_are_simple_with_range_labels(seed):
    """An edge count cannot see a self-loop, a duplicate, or a relabelling."""
    built = _all_generators(seed)
    assert built, "seed produced no valid generator parameters"
    for name, g in built:
        assert _is_simple_with_range_labels(g), name


@pytest.mark.parametrize("seed", range(30))
def test_fixed_seed_reproduces_the_graph(seed):
    """Non-deterministic across seeds, exactly determined within one."""
    for name, g in _all_generators(seed):
        again = dict(_all_generators(seed))[name]
        assert {frozenset(e) for e in g.edges()} == {frozenset(e) for e in again.edges()}
        assert set(g.nodes()) == set(again.nodes())


def test_watts_strogatz_with_zero_rewiring_is_the_ring_lattice():
    """p = 0 removes the randomness entirely, so the output is fully determined."""
    n, k = 10, 4
    ws = fnx.watts_strogatz_graph(n, k, 0.0, seed=1)
    ring = {
        frozenset((i, (i + offset) % n))
        for i in range(n)
        for offset in range(1, k // 2 + 1)
    }
    assert {frozenset(e) for e in ws.edges()} == ring


@pytest.mark.parametrize(
    "case",
    ["ba_m_equals_n", "ba_m_zero", "ws_k_exceeds_n", "regular_odd_product", "regular_d_exceeds_n"],
)
def test_argument_refusals_match_networkx(case):
    """Which arguments are rejected is deterministic, so it IS parity-testable."""
    calls = {
        "ba_m_equals_n": lambda lib: lib.barabasi_albert_graph(5, 5, seed=1),
        "ba_m_zero": lambda lib: lib.barabasi_albert_graph(10, 0, seed=1),
        "ws_k_exceeds_n": lambda lib: lib.watts_strogatz_graph(5, 6, 0.3, seed=1),
        "regular_odd_product": lambda lib: lib.random_regular_graph(3, 5, seed=1),
        "regular_d_exceeds_n": lambda lib: lib.random_regular_graph(6, 5, seed=1),
    }
    call = calls[case]
    got = _raises(lambda: call(fnx))
    want = _raises(lambda: call(nx))

    assert want[0] is not None, "networkx no longer refuses this — retune the case"
    assert got == want
