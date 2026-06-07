"""br-r37-c1-aun4c: set-operator (intersection/difference/symmetric_difference)
verbatim-nx parity.

intersection_all now replicates installed nx's SET-based construction
(node/edge order = CPython set iteration with both orientations for
undirected, in-place &=); intersection is intersection_all([G, H]);
difference / symmetric_difference replicate nx's check sequence and
with_data=False copy depth with batched edge passes (incl. multigraph
keyed edges, previously a full nx round-trip).
"""

import random

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
OPS = ["intersection", "difference", "symmetric_difference"]


def _canon(g):
    edges = (
        sorted(map(repr, g.edges(keys=True, data=True)))
        if g.is_multigraph()
        else [(repr(u), repr(v), d) for u, v, d in g.edges(data=True)]
    )
    return (
        [repr(n) for n in g],
        edges,
        {repr(x): [repr(y) for y in g[x]] for x in g},
        dict(g.graph),
    )


def _build(mod, cls, n, seed):
    g = getattr(mod, cls)()
    r = random.Random(seed)
    g.add_nodes_from(f"n{i}" for i in range(n))
    nodes = list(g)
    for _ in range(n * 3):
        g.add_edge(r.choice(nodes), r.choice(nodes), w=round(r.random(), 6))
    return g


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("op", OPS)
def test_setop_full_order_parity(cls, op):
    for trial in range(3):
        a1, b1 = _build(nx, cls, 25, trial), _build(fnx, cls, 25, trial)
        a2, b2 = _build(nx, cls, 25, trial + 50), _build(fnx, cls, 25, trial + 50)
        assert _canon(getattr(fnx, op)(b1, b2)) == _canon(getattr(nx, op)(a1, a2)), trial


@pytest.mark.parametrize("cls", ["Graph", "MultiGraph", "DiGraph"])
def test_intersection_all_three_graphs(cls):
    a = [_build(nx, cls, 20, s) for s in (1, 2, 3)]
    b = [_build(fnx, cls, 20, s) for s in (1, 2, 3)]
    assert _canon(fnx.intersection_all(b)) == _canon(nx.intersection_all(a))


def test_error_contracts_match_nx_sequence():
    g1n, g1f = nx.Graph([("a", "b")]), fnx.Graph([("a", "b")])
    g2n, g2f = nx.Graph([("a", "c")]), fnx.Graph([("a", "c")])
    m1n, m1f = nx.MultiGraph([("a", "b")]), fnx.MultiGraph([("a", "b")])
    cases = [
        ("difference", (g1n, g2n), (g1f, g2f)),  # node sets unequal
        ("symmetric_difference", (g1n, g2n), (g1f, g2f)),
        ("difference", (g1n, m1n), (g1f, m1f)),  # multigraph mismatch FIRST
        ("intersection", (g1n, m1n), (g1f, m1f)),
    ]
    for op, an, af in cases:
        with pytest.raises(Exception) as nx_err:
            getattr(nx, op)(*an)
        with pytest.raises(Exception) as fnx_err:
            getattr(fnx, op)(*af)
        assert type(fnx_err.value).__name__ == type(nx_err.value).__name__, op
        assert str(fnx_err.value) == str(nx_err.value), op
    with pytest.raises(ValueError) as nx_err:
        nx.intersection_all([])
    with pytest.raises(ValueError) as fnx_err:
        fnx.intersection_all([])
    assert str(fnx_err.value) == str(nx_err.value)


def test_results_carry_no_attrs():
    # nx create_empty_copy(with_data=False): no node/graph attrs; result
    # edges carry no data even when sources are attributed.
    gn1, gf1 = nx.Graph(), fnx.Graph()
    for g in (gn1, gf1):
        g.add_edge("a", "b", w=1)
        g.add_node("c", color="red")
        g.graph["meta"] = 1
    gn2, gf2 = nx.Graph(), fnx.Graph()
    for g in (gn2, gf2):
        g.add_nodes_from(["a", "b", "c"])
        g.add_edge("b", "c", w=9)
    for op in OPS:
        rn, rf = getattr(nx, op)(gn1, gn2), getattr(fnx, op)(gf1, gf2)
        assert _canon(rf) == _canon(rn), op
        assert dict(rf.graph) == {} and all(not d for _, d in rf.nodes(data=True))
