"""Documented divergence + lock for the default ``maximum_flow`` algorithm.

NetworkX's ``maximum_flow``/``maximum_flow_value`` default ``flow_func=None``
resolves to ``preflow_push``. franken_networkx's Rust-native default produces a
flow byte-identical to NetworkX's ``edmonds_karp`` (BFS shortest-augmenting-path)
instead. Consequences:

  * The max-flow **value** and the **min-cut** always match nx (the actual
    contract) — verified here and in the value-parity harness.
  * The returned flow **dict** is a *valid* maximum flow but can differ from
    nx's default whenever the maximum flow is non-unique (different but equally
    optimal edge-by-edge distribution). It equals nx's ``edmonds_karp`` output.
  * An explicit ``flow_func=`` is honored (routed to nx), so passing
    ``flow_func=preflow_push`` reproduces nx's default exactly.

Reproducing ``preflow_push``'s exact non-unique flow distribution in the
Rust-native fast path is not a goal: the value is correct, the result is a
valid max flow, and ``preflow_push``'s specific distribution is an
implementation detail, not part of nx's API contract. This test locks the
behavior so a probe doesn't re-file it and a regression in value-correctness or
flow_func handling is caught. See the intentional-divergences ledger.
"""

import networkx as nx
import franken_networkx as fnx

import pytest

from networkx.algorithms.flow import edmonds_karp, preflow_push

_EDGES = [(0, 1, 3), (0, 2, 2), (1, 2, 1), (1, 3, 2),
          (2, 3, 3), (2, 1, 1), (3, 4, 4), (0, 4, 1)]


def _build(mod):
    g = mod.DiGraph()
    for u, v, c in _EDGES:
        g.add_edge(u, v, capacity=c)
    return g


def test_max_flow_value_matches_networkx():
    assert fnx.maximum_flow_value(_build(fnx), 0, 4) == nx.maximum_flow_value(_build(nx), 0, 4)


def test_min_cut_value_matches_networkx():
    assert fnx.minimum_cut_value(_build(fnx), 0, 4) == nx.minimum_cut_value(_build(nx), 0, 4)


def test_default_flow_dict_equals_edmonds_karp_and_is_valid():
    gf = _build(fnx)
    gn = _build(nx)
    fval, fdict = fnx.maximum_flow(gf, 0, 4)
    # fnx default == nx edmonds_karp (byte-for-byte)
    assert fdict == nx.maximum_flow(gn, 0, 4, flow_func=edmonds_karp)[1]
    # ...and it is a genuine max flow: value out of source equals the max value
    assert sum(fdict[0].values()) == fval == nx.maximum_flow_value(gn, 0, 4)
    # capacity respected
    cap = {(u, v): c for u, v, c in _EDGES}
    for u, nbrs in fdict.items():
        for v, f in nbrs.items():
            assert 0 <= f <= cap[(u, v)]
    # conservation at internal nodes
    for n in (1, 2, 3):
        inflow = sum(fdict[u].get(n, 0) for u in fdict)
        outflow = sum(fdict[n].values())
        assert inflow == outflow


def test_explicit_flow_func_is_honored():
    # Passing flow_func=preflow_push must reproduce nx's default exactly.
    gf = _build(fnx)
    gn = _build(nx)
    assert (
        fnx.maximum_flow(gf, 0, 4, flow_func=preflow_push)[1]
        == nx.maximum_flow(gn, 0, 4, flow_func=preflow_push)[1]
    )
