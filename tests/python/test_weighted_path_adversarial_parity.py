"""Adversarial weighted shortest-path differential parity vs networkx.

br-r37-c1-wpathfuzz: weighted shortest paths are a documented bug-density area
(SPFA processing-order tie-breaks, dijkstra finalize/dict order, negative-weight
Bellman-Ford, negative-cycle detection). This deterministically fuzzes random
weighted graphs and asserts EXACT parity vs networkx for:

  * dijkstra_path_length (non-negative)
  * dijkstra_path VALUE (equal-length tie-break selection)
  * single_source_bellman_ford_path_length with NEGATIVE weights (directed)
  * negative_edge_cycle detection (directed)

fnx is byte-exact here (validated 0 mismatches over 22k+ checks at authoring);
this locks that against regressions. Uses exact ``==`` (not tolerance) because
the paths/lengths are integer-weighted and the selections are deterministic.
"""

import random

import networkx as nx
import pytest

import franken_networkx as fnx


def _build(seed, directed, allow_neg):
    rng = random.Random(seed)
    fcls = fnx.DiGraph if directed else fnx.Graph
    ncls = nx.DiGraph if directed else nx.Graph
    Gf, Gn = fcls(), ncls()
    n = rng.randint(4, 8)
    for _ in range(rng.randint(n, n * 3)):
        a, b = rng.randrange(n), rng.randrange(n)
        if a == b:
            continue
        w = rng.randint(-3, 6) if allow_neg else rng.randint(1, 6)
        Gf.add_edge(a, b, weight=w)
        Gn.add_edge(a, b, weight=w)
    return Gf, Gn


def _both(ff, nf):
    """Return (fnx_result, nx_result), mapping exceptions to a comparable tag."""
    try:
        rf = ff()
    except Exception as e:  # noqa: BLE001 - parity includes error type
        rf = ("EXC", type(e).__name__)
    try:
        rn = nf()
    except Exception as e:  # noqa: BLE001
        rn = ("EXC", type(e).__name__)
    return rf, rn


@pytest.mark.parametrize("directed", [False, True])
def test_dijkstra_path_and_length_parity(directed):
    mismatches = []
    for seed in range(300):
        Gf, Gn = _build(seed, directed, allow_neg=False)
        nodes = sorted(set(Gn.nodes()) & set(Gf.nodes()))
        for s in nodes[:3]:
            for t in nodes[:3]:
                if s == t:
                    continue
                rf, rn = _both(
                    lambda s=s, t=t: fnx.dijkstra_path_length(Gf, s, t, weight="weight"),
                    lambda s=s, t=t: nx.dijkstra_path_length(Gn, s, t, weight="weight"),
                )
                if rf != rn:
                    mismatches.append(("len", seed, s, t, rf, rn))
                rf, rn = _both(
                    lambda s=s, t=t: fnx.dijkstra_path(Gf, s, t, weight="weight"),
                    lambda s=s, t=t: nx.dijkstra_path(Gn, s, t, weight="weight"),
                )
                if rf != rn:
                    mismatches.append(("path", seed, s, t, rf, rn))
    assert not mismatches, (
        f"dijkstra divergence (directed={directed}): {len(mismatches)}; "
        f"first={mismatches[0]}"
    )


def test_bellman_ford_negative_and_cycle_parity():
    mismatches = []
    for seed in range(400):
        Gf, Gn = _build(seed, directed=True, allow_neg=True)
        nodes = sorted(set(Gn.nodes()) & set(Gf.nodes()))
        for s in nodes[:2]:
            rf, rn = _both(
                lambda s=s: dict(
                    fnx.single_source_bellman_ford_path_length(Gf, s, weight="weight")
                ),
                lambda s=s: dict(
                    nx.single_source_bellman_ford_path_length(Gn, s, weight="weight")
                ),
            )
            if rf != rn:
                mismatches.append(("bf_len", seed, s, rf, rn))
        rf, rn = _both(
            lambda: fnx.negative_edge_cycle(Gf, weight="weight"),
            lambda: nx.negative_edge_cycle(Gn, weight="weight"),
        )
        if rf != rn:
            mismatches.append(("negcycle", seed, rf, rn))
    assert not mismatches, f"bellman-ford divergence: {len(mismatches)}; first={mismatches[0]}"
