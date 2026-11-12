"""Regression lock for default ``maximum_flow`` and ``minimum_cut`` parity with NetworkX.

NetworkX's ``maximum_flow``, ``maximum_flow_value``, ``minimum_cut``, and
``minimum_cut_value`` default ``flow_func=None`` resolves to ``preflow_push``.
franken_networkx's Rust-native default now executes ``preflow_push`` (with the
exact bidirectional BFS initial heights, reverse-edge initialization, excess
queues, and gap relabeling) so that:

  * The max-flow **value** and the returned flow **dict** match ``nx.maximum_flow``
    byte-for-byte on both directed and undirected graphs (``br-r37-c1-uh5ua``).
  * The min-cut **value** and ``(reachable, non_reachable)`` node partition match
    ``nx.minimum_cut`` exactly.
  * Callers that default to ``edmonds_karp`` in NetworkX (``minimum_node_cut``,
    ``minimum_edge_cut``, ``gomory_hu_tree``) continue to use the Edmonds-Karp
    residual partition.
  * Passing an explicit ``flow_func=`` (such as ``edmonds_karp`` or
    ``preflow_push``) is honored and matches NetworkX.
"""

import networkx as nx
import franken_networkx as fnx

from networkx.algorithms.flow import edmonds_karp, preflow_push

_EDGES = [(0, 1, 3), (0, 2, 2), (1, 2, 1), (1, 3, 2),
          (2, 3, 3), (2, 1, 1), (3, 4, 4), (0, 4, 1)]


def _build(mod, directed=True):
    g = mod.DiGraph() if directed else mod.Graph()
    for u, v, c in _EDGES:
        g.add_edge(u, v, capacity=c)
    return g


def test_max_flow_value_matches_networkx():
    assert fnx.maximum_flow_value(_build(fnx), 0, 4) == nx.maximum_flow_value(_build(nx), 0, 4)
    assert fnx.maximum_flow_value(_build(fnx, False), 0, 4) == nx.maximum_flow_value(_build(nx, False), 0, 4)


def test_min_cut_matches_networkx():
    assert fnx.minimum_cut_value(_build(fnx), 0, 4) == nx.minimum_cut_value(_build(nx), 0, 4)
    assert fnx.minimum_cut(_build(fnx), 0, 4) == nx.minimum_cut(_build(nx), 0, 4)
    assert fnx.minimum_cut(_build(fnx, False), 0, 4) == nx.minimum_cut(_build(nx, False), 0, 4)


def test_default_flow_dict_equals_preflow_push_and_is_valid():
    for directed in (True, False):
        gf = _build(fnx, directed=directed)
        gn = _build(nx, directed=directed)
        fval, fdict = fnx.maximum_flow(gf, 0, 4)
        nx_val, nx_dict = nx.maximum_flow(gn, 0, 4)
        assert fval == nx_val
        assert fdict == nx_dict
        assert fdict == nx.maximum_flow(gn, 0, 4, flow_func=preflow_push)[1]
        assert sum(fdict[0].values()) - sum(fdict[u].get(0, 0) for u in fdict) == fval
        for n in (1, 2, 3):
            inflow = sum(fdict[u].get(n, 0) for u in fdict)
            outflow = sum(fdict[n].values())
            assert inflow == outflow


def test_explicit_flow_func_is_honored():
    gf = _build(fnx)
    gn = _build(nx)
    assert (
        fnx.maximum_flow(gf, 0, 4, flow_func=preflow_push)[1]
        == nx.maximum_flow(gn, 0, 4, flow_func=preflow_push)[1]
    )
    assert (
        fnx.maximum_flow(gf, 0, 4, flow_func=edmonds_karp)[1]
        == nx.maximum_flow(gn, 0, 4, flow_func=edmonds_karp)[1]
    )


def test_edmonds_karp_default_callers_preserve_parity():
    gf = _build(fnx, directed=False)
    gn = _build(nx, directed=False)
    assert fnx.minimum_node_cut(gf, 0, 4) == nx.minimum_node_cut(gn, 0, 4)
    assert fnx.minimum_edge_cut(gf, 0, 4) == nx.minimum_edge_cut(gn, 0, 4)
    tf = fnx.gomory_hu_tree(gf)
    tn = nx.gomory_hu_tree(gn)
    assert sorted(tf.edges(data=True)) == sorted(tn.edges(data=True))

