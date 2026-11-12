"""br-r37-c1-kmxke: union/disjoint_union/relabel batched-construction parity.

union_all's per-edge loops and relabel_nodes' copy path now batch through
add_edges_from; union(rename=...) routes through the native union_all
instead of an nx round-trip. These tests pin full ordering parity across
all four classes, rename forms, node-merging relabels, and error paths.
"""

import random

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


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


def _build(mod, cls, n, seed, intkeys=False):
    g = getattr(mod, cls)()
    r = random.Random(seed)
    g.add_nodes_from(range(n) if intkeys else (f"{cls}{i}" for i in range(n)))
    nodes = list(g)
    for _ in range(n * 2):
        u, v = r.choice(nodes), r.choice(nodes)
        if r.random() < 0.7:
            g.add_edge(u, v, w=round(r.random(), 9))
        else:
            g.add_edge(u, v)
    return g


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("intkeys", [False, True])
@pytest.mark.parametrize("rename", [(), ("x-", "y-"), ("p",)])
def test_union_parity(cls, intkeys, rename):
    a1, b1 = _build(nx, cls, 25, 1, intkeys), _build(fnx, cls, 25, 1, intkeys)
    a2, b2 = _build(nx, cls, 15, 2, intkeys), _build(fnx, cls, 15, 2, intkeys)
    kw = {"rename": rename} if rename else {}
    try:
        cn, en = _canon(nx.union(a1, a2, **kw)), None
    except Exception as e:
        cn, en = None, (type(e).__name__, str(e))
    try:
        cf, ef = _canon(fnx.union(b1, b2, **kw)), None
    except Exception as e:
        cf, ef = None, (type(e).__name__, str(e))
    assert cn == cf and en == ef


@pytest.mark.parametrize("cls", CLASSES)
def test_disjoint_union_parity(cls):
    a1, b1 = _build(nx, cls, 25, 3), _build(fnx, cls, 25, 3)
    a2, b2 = _build(nx, cls, 15, 4), _build(fnx, cls, 15, 4)
    assert _canon(nx.disjoint_union(a1, a2)) == _canon(fnx.disjoint_union(b1, b2))


@pytest.mark.parametrize("cls", ["Graph", "DiGraph"])
def test_relabel_copy_parity_incl_node_merge(cls):
    a, b = _build(nx, cls, 25, 5), _build(fnx, cls, 25, 5)
    nodes = list(a)
    merge = {nodes[0]: "M", nodes[1]: "M", nodes[2]: "Z"}
    assert _canon(nx.relabel_nodes(a, merge)) == _canon(fnx.relabel_nodes(b, merge))
    full = {n: f"r{i}" for i, n in enumerate(nodes)}
    assert _canon(nx.relabel_nodes(a, full)) == _canon(fnx.relabel_nodes(b, full))


def test_union_collision_error_parity():
    gn, gf = nx.Graph([("a", "b")]), fnx.Graph([("a", "b")])
    with pytest.raises(Exception) as nx_err:
        nx.union(gn, gn)
    with pytest.raises(Exception) as fnx_err:
        fnx.union(gf, gf)
    assert type(fnx_err.value).__name__ == type(nx_err.value).__name__
    assert str(fnx_err.value) == str(nx_err.value)
