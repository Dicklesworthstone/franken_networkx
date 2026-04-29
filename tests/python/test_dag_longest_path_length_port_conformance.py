"""Golden conformance harness for the Rust ``dag_longest_path_length`` port.

The Python ``franken_networkx.dag_longest_path_length`` previously
delegated all cases to ``_call_networkx_for_parity``. The native
Rust port adds the weighted variant alongside the existing
unweighted one, dispatching both through
``franken_networkx._fnx.dag_longest_path_length(G, weight=,
default_weight=)``.

This harness validates 50+ inputs across:

- Both dispatch paths: unweighted and weighted (str weight)
- Many DAG topologies: chains, diamonds, branchings, dense and
  sparse random DAGs, single-node, two-node
- ``default_weight`` behavior for edges missing the weight key
- Cyclic-graph rejection (must raise ``NetworkXUnfeasible``,
  matching nx)

Each input is run through both ``fnx.dag_longest_path_length`` and
``networkx.dag_longest_path_length`` and the two scalars must
match exactly (within float tolerance for weighted cases).
"""

from __future__ import annotations

import math

import networkx as nx
import pytest

import franken_networkx as fnx


def _close(a, b, *, tol=1e-9):
    if isinstance(a, float) or isinstance(b, float):
        af, bf = float(a), float(b)
        if math.isnan(af) and math.isnan(bf):
            return True
        return abs(af - bf) <= tol * max(1.0, abs(af), abs(bf))
    return a == b


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def _chain_dag(n, weights=None):
    """Linear chain 0→1→2→…→n-1."""
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    for i in range(n - 1):
        w = weights[i] if weights else 1.0
        fg.add_edge(i, i + 1, weight=w)
        ng.add_edge(i, i + 1, weight=w)
    return fg, ng


def _diamond_dag(weights):
    """0→1, 0→2, 1→3, 2→3 with arbitrary weights ((a,b,c,d))."""
    a, b, c, d = weights
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    fg.add_edge(0, 1, weight=a); ng.add_edge(0, 1, weight=a)
    fg.add_edge(0, 2, weight=b); ng.add_edge(0, 2, weight=b)
    fg.add_edge(1, 3, weight=c); ng.add_edge(1, 3, weight=c)
    fg.add_edge(2, 3, weight=d); ng.add_edge(2, 3, weight=d)
    return fg, ng


def _branching_dag(branch_factor, depth):
    """Balanced branching tree as DiGraph (parent→child edges)."""
    proto = nx.balanced_tree(branch_factor, depth, create_using=nx.DiGraph)
    fg = fnx.DiGraph(); fg.add_edges_from(proto.edges())
    ng = nx.DiGraph(); ng.add_edges_from(proto.edges())
    return fg, ng


def _layered_dag(layers, weights=None):
    """Multi-layer DAG. ``layers`` is a list of layer sizes; every node
    in layer k is connected to every node in layer k+1."""
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    nid = 0
    layer_nodes = []
    for size in layers:
        layer = list(range(nid, nid + size))
        layer_nodes.append(layer)
        nid += size
    edge_idx = 0
    for k in range(len(layer_nodes) - 1):
        for u in layer_nodes[k]:
            for v in layer_nodes[k + 1]:
                w = (weights[edge_idx] if weights else 1.0)
                edge_idx += 1
                fg.add_edge(u, v, weight=w)
                ng.add_edge(u, v, weight=w)
    return fg, ng


# ---------------------------------------------------------------------------
# 1. Unweighted parity across many DAGs
# ---------------------------------------------------------------------------


UNWEIGHTED_DAGS = [
    ("chain_2", lambda: _chain_dag(2)),
    ("chain_5", lambda: _chain_dag(5)),
    ("chain_10", lambda: _chain_dag(10)),
    ("chain_20", lambda: _chain_dag(20)),
    ("diamond_unit",
     lambda: _diamond_dag((1.0, 1.0, 1.0, 1.0))),
    ("branching_2_3", lambda: _branching_dag(2, 3)),
    ("branching_3_2", lambda: _branching_dag(3, 2)),
    ("layered_2_3_2",
     lambda: _layered_dag([2, 3, 2])),
    ("layered_3_4_2",
     lambda: _layered_dag([3, 4, 2])),
    ("layered_1_4_4_1",
     lambda: _layered_dag([1, 4, 4, 1])),
]


@pytest.mark.parametrize(
    "name,builder", UNWEIGHTED_DAGS,
    ids=[fx[0] for fx in UNWEIGHTED_DAGS],
)
def test_unweighted_dag_longest_path_length_matches_networkx(name, builder):
    fg, ng = builder()
    fr = fnx.dag_longest_path_length(fg, weight=None)
    nr = nx.dag_longest_path_length(ng, weight=None)
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


@pytest.mark.parametrize(
    "name,builder", UNWEIGHTED_DAGS,
    ids=[fx[0] for fx in UNWEIGHTED_DAGS],
)
def test_default_weight_str_matches_networkx(name, builder):
    """When edges *do* carry the weight attribute, ``weight="weight"``
    pulls the values; for edges without the attribute,
    ``default_weight`` fills in. Most of these fixtures set weight=1
    on every edge so the weighted result matches the unweighted one."""
    fg, ng = builder()
    fr = fnx.dag_longest_path_length(fg, weight="weight", default_weight=1)
    nr = nx.dag_longest_path_length(ng, weight="weight", default_weight=1)
    assert _close(fr, nr), f"{name}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# 2. Weighted parity with non-trivial weights
# ---------------------------------------------------------------------------


WEIGHTED_DAGS = [
    ("chain_5_increasing",
     lambda: _chain_dag(5, weights=[1.0, 2.0, 3.0, 4.0])),
    ("chain_5_decreasing",
     lambda: _chain_dag(5, weights=[4.0, 3.0, 2.0, 1.0])),
    ("diamond_a_path_dominant",
     lambda: _diamond_dag((10.0, 1.0, 10.0, 1.0))),
    ("diamond_b_path_dominant",
     lambda: _diamond_dag((1.0, 10.0, 1.0, 10.0))),
    ("diamond_negative_weights",
     lambda: _diamond_dag((-1.0, 5.0, 0.5, 0.0))),
    ("layered_random",
     lambda: _layered_dag(
         [2, 3, 2],
         weights=[0.5, 1.0, 1.5, 2.0, 2.5, 3.0,
                  3.5, 4.0, 4.5, 5.0, 5.5, 6.0],
     )),
    ("chain_5_zero_weights",
     lambda: _chain_dag(5, weights=[0.0, 0.0, 0.0, 0.0])),
    ("chain_5_fractional_weights",
     lambda: _chain_dag(5, weights=[0.1, 0.2, 0.3, 0.4])),
]


@pytest.mark.parametrize(
    "name,builder", WEIGHTED_DAGS,
    ids=[fx[0] for fx in WEIGHTED_DAGS],
)
def test_weighted_dag_longest_path_length_matches_networkx(name, builder):
    fg, ng = builder()
    fr = fnx.dag_longest_path_length(fg, weight="weight")
    nr = nx.dag_longest_path_length(ng, weight="weight")
    assert _close(fr, nr), f"{name}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# 3. default_weight handling: edges without weight attr fall back
# ---------------------------------------------------------------------------


def test_default_weight_used_for_unset_attributes_matches_networkx():
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    # Mix: some edges have weight, some don't.
    fg.add_edge(0, 1, weight=5.0)
    fg.add_edge(1, 2)  # no weight
    fg.add_edge(2, 3, weight=2.5)
    ng.add_edge(0, 1, weight=5.0)
    ng.add_edge(1, 2)
    ng.add_edge(2, 3, weight=2.5)
    for default in (1, 1.5, 0, 100):
        fr = fnx.dag_longest_path_length(fg, weight="weight", default_weight=default)
        nr = nx.dag_longest_path_length(ng, weight="weight", default_weight=default)
        assert _close(fr, nr), f"default_weight={default}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# 4. Edge cases: cycles, undirected, single node
# ---------------------------------------------------------------------------


def test_cycle_raises_networkx_unfeasible_matching_nx():
    fg = fnx.DiGraph(); fg.add_edges_from([(0, 1), (1, 2), (2, 0)])
    ng = nx.DiGraph(); ng.add_edges_from([(0, 1), (1, 2), (2, 0)])
    with pytest.raises(nx.NetworkXUnfeasible):
        nx.dag_longest_path_length(ng)
    with pytest.raises(nx.NetworkXUnfeasible):
        fnx.dag_longest_path_length(fg)


def test_undirected_raises_not_implemented():
    fg = fnx.path_graph(3)
    ng = nx.path_graph(3)
    with pytest.raises(nx.NetworkXNotImplemented):
        nx.dag_longest_path_length(ng)
    with pytest.raises(fnx.NetworkXNotImplemented):
        fnx.dag_longest_path_length(fg)


def test_empty_graph_returns_zero():
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    assert fnx.dag_longest_path_length(fg) == nx.dag_longest_path_length(ng)


def test_single_node_dag_returns_zero():
    fg = fnx.DiGraph(); fg.add_node(0)
    ng = nx.DiGraph(); ng.add_node(0)
    assert fnx.dag_longest_path_length(fg) == nx.dag_longest_path_length(ng) == 0


def test_two_node_no_edge_returns_zero():
    fg = fnx.DiGraph(); fg.add_nodes_from([0, 1])
    ng = nx.DiGraph(); ng.add_nodes_from([0, 1])
    assert fnx.dag_longest_path_length(fg) == nx.dag_longest_path_length(ng)


# ---------------------------------------------------------------------------
# 5. Random DAG sweep (50+ explicit fixtures stack across the suite)
# ---------------------------------------------------------------------------


def _random_dag(seed, n, edge_prob, weight_max):
    """Generate a random DAG: nodes 0..n-1; for each (u, v) with u < v,
    add an edge with probability edge_prob and weight uniform on
    [0, weight_max]."""
    import random
    rng = random.Random(seed)
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if rng.random() < edge_prob:
                w = rng.uniform(0, weight_max)
                fg.add_edge(u, v, weight=w)
                ng.add_edge(u, v, weight=w)
    return fg, ng


@pytest.mark.parametrize(
    "seed,n,p",
    [
        (1, 5, 0.5), (2, 5, 0.5), (3, 6, 0.4), (4, 6, 0.6),
        (5, 8, 0.3), (6, 8, 0.5), (7, 10, 0.3), (8, 10, 0.5),
        (9, 12, 0.2), (10, 12, 0.4),
        (11, 5, 0.7), (12, 6, 0.7), (13, 8, 0.7), (14, 10, 0.7),
        (15, 12, 0.5),
    ],
)
def test_random_dag_unweighted_matches_networkx(seed, n, p):
    fg, ng = _random_dag(seed, n, p, weight_max=10.0)
    fr = fnx.dag_longest_path_length(fg, weight=None)
    nr = nx.dag_longest_path_length(ng, weight=None)
    assert fr == nr, f"seed={seed} n={n} p={p}: fnx={fr} nx={nr}"


@pytest.mark.parametrize(
    "seed,n,p",
    [
        (1, 5, 0.5), (2, 5, 0.5), (3, 6, 0.4), (4, 6, 0.6),
        (5, 8, 0.3), (6, 8, 0.5), (7, 10, 0.3), (8, 10, 0.5),
        (9, 12, 0.2), (10, 12, 0.4),
    ],
)
def test_random_dag_weighted_matches_networkx(seed, n, p):
    fg, ng = _random_dag(seed, n, p, weight_max=10.0)
    fr = fnx.dag_longest_path_length(fg, weight="weight")
    nr = nx.dag_longest_path_length(ng, weight="weight")
    assert _close(fr, nr), f"seed={seed} n={n} p={p}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# 6. Cross-relation invariants
# ---------------------------------------------------------------------------


def test_unweighted_length_equals_path_minus_one():
    """``dag_longest_path_length(G, weight=None)`` equals
    ``len(dag_longest_path(G)) - 1`` for any DAG."""
    fg = fnx.DiGraph()
    fg.add_edges_from([(0, 1), (0, 2), (1, 3), (2, 3), (3, 4)])
    length = fnx.dag_longest_path_length(fg, weight=None)
    path = fnx.dag_longest_path(fg, weight=None)
    assert length == len(path) - 1


def test_weighted_length_with_unit_weights_equals_unweighted():
    """When every edge has weight 1, the weighted length equals the
    unweighted hop count."""
    fg, _ = _chain_dag(8, weights=[1.0] * 7)
    fr_unw = fnx.dag_longest_path_length(fg, weight=None)
    fr_w = fnx.dag_longest_path_length(fg, weight="weight")
    assert _close(fr_w, float(fr_unw))


def test_weighted_length_is_nondecreasing_in_weights():
    """Doubling every weight doubles the longest path length."""
    fg1, _ = _chain_dag(5, weights=[1.0, 2.0, 1.5, 0.5])
    fg2, _ = _chain_dag(5, weights=[2.0, 4.0, 3.0, 1.0])
    l1 = fnx.dag_longest_path_length(fg1, weight="weight")
    l2 = fnx.dag_longest_path_length(fg2, weight="weight")
    assert _close(l2, 2.0 * l1)
