"""constraint(DiGraph, nodes=<iterable>) uses a native kernel and matches networkx.

br-r37-c1-qbj9u. networkx serves ``constraint`` TWO ways and they DISAGREE on directed
graphs: ``nodes is None and has_scipy`` takes a sparse-matrix path (P + P.T, row
normalised), anything else takes the set-order summation over ``local_constraint``.
Measured, they differ on 19 of 40 random digraphs, and the difference is specifically
NaN PLACEMENT rather than values: a node with predecessors but NO successors gets a number
from the matrix path and NaN from the loop. (That is narrower than the sibling
``effective_size``, where the two paths return genuinely different numbers - 2.0 against
1.8 on one 6-node graph. Do not carry that assumption across.) So whichever kernel serves
``nodes != None`` must reproduce the LOOP, and the ``nodes is None`` branch must keep the
matrix answer - they are not interchangeable.

Before this, the ``nodes != None`` branch delegated wholesale and measured 0.964x against
networkx at 2.59e9 Ir/call - fnx running networkx's own loop plus a graph conversion. The
native ``constraint_directed_rust`` kernel takes it to 306.7x (8.15M Ir/call).

The kernel could not simply reuse ``constraint_rust``: that one is UNDIRECTED-only and
misses networkx's directed answer on 548 of 807 node values, and not by rounding (0.269
against 0.31).

THE RULE THAT IS EASY TO GET WRONG, and which kept the sibling
``effective_size_directed_rust`` reverted for months: networkx marks a node NaN when
``len(G[v]) == 0``, and ``G[v]`` on a DiGraph is SUCCESSORS ONLY - a node with predecessors
but no successors is NaN. ``local_constraint`` also normalises with ``sum`` for BOTH
factors, unlike ``redundancy`` in ``effective_size``, which uses ``norm=max`` for the
second - carrying the sibling's formula across unchanged would be wrong.
"""

import random

import networkx as nx
import pytest

import franken_networkx as fnx


def _same(a, b):
    assert set(a) == set(b)
    for key in a:
        av, bv = a[key], b[key]
        a_nan = isinstance(av, float) and av != av
        b_nan = isinstance(bv, float) and bv != bv
        assert a_nan == b_nan, key
        if not a_nan:
            assert av == pytest.approx(bv, abs=1e-9), key


def _build(module, n, seed, permute):
    rng = random.Random(seed)
    graph = module.DiGraph()
    labels = list(range(n))
    if permute:
        rng.shuffle(labels)
    graph.add_nodes_from(labels)
    for i in range(n):
        for _ in range(rng.choice([0, 1, 3])):
            j = rng.randrange(n)
            if i != j:
                graph.add_edge(labels[i], labels[j])
    return graph, labels


@pytest.mark.parametrize("permute", [False, True])
@pytest.mark.parametrize("seed", range(12))
def test_directed_subset_constraint_matches_networkx(seed, permute):
    n = random.Random(seed).randint(1, 25)
    fg, labels = _build(fnx, n, seed, permute)
    ng, _ = _build(nx, n, seed, permute)
    for nodes in (list(labels), [labels[0]], sorted(labels[: max(1, n // 2)])):
        _same(fnx.constraint(fg, nodes=nodes), nx.constraint(ng, nodes=nodes))


def test_directed_subset_uses_the_native_route(monkeypatch):
    """A regression that quietly re-delegates this branch must fail here."""
    fg = fnx.DiGraph([(0, 1), (1, 2), (2, 0), (2, 3), (3, 1), (4, 0)])
    ng = nx.DiGraph([(0, 1), (1, 2), (2, 0), (2, 3), (3, 1), (4, 0)])

    def fail_fallback(*args, **kwargs):
        raise AssertionError("directed constraint(nodes=...) must use the native kernel")

    monkeypatch.setattr(fnx, "_call_networkx_submodule_for_parity", fail_fallback)
    monkeypatch.setattr(fnx, "_structural_holes_constraint_matrix", fail_fallback)
    _same(fnx.constraint(fg, nodes=list(fg)), nx.constraint(ng, nodes=list(ng)))


def test_nodes_none_must_keep_the_matrix_path():
    """And nodes=None must NOT use that kernel, because networkx does not.

    If networkx ever reconciles its two paths, the assert below fires and tells the next
    person to re-derive which kernel this branch needs.
    """
    # A graph where networkx's two constraint paths demonstrably differ. Node 1 has
    # predecessors {0, 2, 3} and NO successors: the matrix path gives it 0.534722, the
    # loop gives NaN. Picked by search - the fixture that separates the two paths for
    # effective_size does NOT separate them here, which is why this carries its own.
    edges = [(0, 1), (0, 4), (2, 0), (2, 1), (3, 1), (4, 0), (4, 3)]
    fg, ng = fnx.DiGraph(edges), nx.DiGraph(edges)
    fg.add_nodes_from(range(5))
    ng.add_nodes_from(range(5))

    default = nx.constraint(ng)
    loop = nx.constraint(ng, nodes=list(ng))
    assert any(
        (default[k] != default[k]) != (loop[k] != loop[k]) for k in default
    ), "networkx's two constraint paths agree here now; re-derive this branch"
    _same(fnx.constraint(fg), default)
    _same(fnx.constraint(fg, nodes=list(fg)), loop)


def test_weighted_selfloop_and_multigraph_keep_the_delegated_route():
    """The native kernel is unweighted, simple and self-loop-free; everything else stays."""
    weighted_f, weighted_n = fnx.DiGraph(), nx.DiGraph()
    for graph in (weighted_f, weighted_n):
        graph.add_edge(0, 1, weight=3.0)
        graph.add_edge(1, 2, weight=1.0)
        graph.add_edge(2, 0, weight=2.0)
    _same(
        fnx.constraint(weighted_f, nodes=list(weighted_f), weight="weight"),
        nx.constraint(weighted_n, nodes=list(weighted_n), weight="weight"),
    )

    loop_f, loop_n = fnx.DiGraph(), nx.DiGraph()
    for graph in (loop_f, loop_n):
        graph.add_edges_from([(0, 0), (0, 1), (1, 2), (2, 0)])
    _same(fnx.constraint(loop_f, nodes=list(loop_f)), nx.constraint(loop_n, nodes=list(loop_n)))

    multi_f, multi_n = fnx.MultiDiGraph(), nx.MultiDiGraph()
    for graph in (multi_f, multi_n):
        graph.add_edges_from([(0, 1), (0, 1), (1, 2), (2, 0)])
    _same(fnx.constraint(multi_f, nodes=list(multi_f)), nx.constraint(multi_n, nodes=list(multi_n)))
