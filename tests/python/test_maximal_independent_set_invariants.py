"""maximal_independent_set invariants (independent + maximal + dominating).

maximal_independent_set is randomized (it depends on seed-driven choices and
does not match networkx value-for-value), so it is validated by its defining
PROPERTIES rather than by parity:
  - independence: no two chosen nodes are adjacent;
  - maximality: every non-chosen node is adjacent to a chosen one (otherwise it
    could be added);
  - a maximal independent set is necessarily a DOMINATING set;
  - any nodes passed as the required seed set are included.
These oracle-free invariants hold for whatever valid MIS is returned.

Being randomized rules out value parity, but NOT contract parity: which inputs
are refused is deterministic, so the refusals are compared against networkx
directly. Three of them exist and none was exercised — required nodes that are
adjacent to each other, a required node absent from the graph, and a directed
graph. The seeded output is also reproducible, and the existing `nodes` test
forces exactly one node, so a multi-node required set is covered here too.

No mocks: real fnx.
"""

from __future__ import annotations

import random

import networkx as nx
import pytest
import franken_networkx as fnx


def _graph(seed):
    r = random.Random(seed)
    n = r.randint(5, 11)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.35]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)
    return g, n


@pytest.mark.parametrize("seed", range(40))
def test_mis_is_independent_and_maximal(seed):
    g, n = _graph(seed)
    adj = {node: set(g.neighbors(node)) for node in g}
    mis = set(fnx.maximal_independent_set(g, seed=seed))

    # Independence: no edge inside the set.
    for u in mis:
        assert not (adj[u] & mis - {u})
    # Maximality: every node outside has a neighbor inside.
    for node in g:
        if node not in mis:
            assert adj[node] & mis


@pytest.mark.parametrize("seed", range(40))
def test_mis_is_a_dominating_set(seed):
    g, n = _graph(seed)
    mis = set(fnx.maximal_independent_set(g, seed=seed))
    # A maximal independent set is always a dominating set.
    assert fnx.is_dominating_set(g, mis)


@pytest.mark.parametrize("seed", range(20))
def test_required_seed_nodes_are_included(seed):
    g, n = _graph(seed)
    first = list(g.nodes())[0]
    mis = set(fnx.maximal_independent_set(g, nodes=[first], seed=seed))
    assert first in mis
    # Still independent and dominating with the forced seed.
    assert fnx.is_dominating_set(g, mis)


def _as_networkx(g):
    ng = nx.Graph()
    ng.add_nodes_from(g.nodes())
    ng.add_edges_from(g.edges())
    return ng


def _raises(fn):
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 - the type IS the assertion
        return type(exc).__name__, str(exc)
    return None, None


@pytest.mark.parametrize("case", ["adjacent_required", "foreign_required", "directed"])
def test_refusal_contracts_match_networkx(case):
    """Randomness rules out value parity; which inputs are REFUSED is exact."""
    g, _ = _graph(3)

    if case == "directed":
        d = fnx.DiGraph(); d.add_edges_from([(0, 1), (1, 2)])
        nd = nx.DiGraph([(0, 1), (1, 2)])
        got = _raises(lambda: fnx.maximal_independent_set(d, seed=1))
        want = _raises(lambda: nx.maximal_independent_set(nd, seed=1))
    else:
        # Two adjacent nodes cannot both be in an independent set; a node that is
        # not in the graph cannot be in any of its subsets.
        nodes = list(next(iter(g.edges()))) if case == "adjacent_required" else ["absent"]
        got = _raises(lambda: fnx.maximal_independent_set(g, nodes=nodes, seed=1))
        want = _raises(lambda: nx.maximal_independent_set(_as_networkx(g), nodes=nodes, seed=1))

    assert want[0] is not None, "networkx no longer refuses this — retune the case"
    assert got == want


@pytest.mark.parametrize("seed", range(20))
def test_multiple_required_nodes_are_all_included(seed):
    """The existing seed-node test forces exactly one node."""
    g, _ = _graph(seed)
    required = []
    for v in g.nodes():
        if all(not g.has_edge(v, w) for w in required):
            required.append(v)
        if len(required) == 3:
            break
    if len(required) < 2:
        pytest.skip("no independent pair available")

    mis = set(fnx.maximal_independent_set(g, nodes=required, seed=seed))
    assert set(required) <= mis
    assert fnx.is_dominating_set(g, mis)


@pytest.mark.parametrize("seed", range(40))
def test_result_is_a_nonempty_list_of_graph_nodes(seed):
    """The property tests would all pass on a set of nodes from somewhere else."""
    g, _ = _graph(seed)
    mis = fnx.maximal_independent_set(g, seed=seed)
    assert isinstance(mis, list)
    assert set(mis) <= set(g.nodes())
    assert mis                      # a graph with nodes always has a nonempty MIS
    assert len(set(mis)) == len(mis)     # no node reported twice


@pytest.mark.parametrize("seed", range(20))
def test_same_seed_is_reproducible(seed):
    """Randomized, but not unpredictable: a fixed seed pins the output."""
    g, _ = _graph(seed)
    assert fnx.maximal_independent_set(g, seed=seed) == fnx.maximal_independent_set(g, seed=seed)
