"""Undirected multigraph shortest paths settle nodes in networkx's order (br-r37-c1-yqfw9).

The Bellman-Ford routes collapse parallel edges to a simple min-weight graph and run
the simple kernel on it. That graph got its pairs in edge order, so a node's row
listed its neighbours in another order than the multigraph's own row; the kernel
relaxes a row in order, so nodes at equal distance settled in another order and
single_source_bellman_ford_path_length iterated differently from networkx's (21 of
these cases failed on main de58cd218). The collapse now adds its pairs in row order.
The Dijkstra calls run natively (br-r37-c1-bow4p) and stay here as a guard; the
kept-collapse test walks the cached Bellman-Ford collapse (br-r37-c1-w2e8e) through
every kind of write.

Written in the fnx-rc1004-a/b worktrees for bow4p and never landed until this fix.

No mocks: real fnx against real networkx, both graphs from one edge list,
results compared in order and with their types.
"""


from __future__ import annotations

import math
import random

import pytest
import networkx as nx
import franken_networkx as fnx

WEIGHTS = {
    "int": lambda r: r.randint(1, 9),
    "float": lambda r: r.choice([0.5, 1.25, 2.0, 3.5]),
    "mixed": lambda r: r.choice([1, 2.0, 3, 0.5, True]),
    "missing": lambda r: None,
    "negative": lambda r: r.choice([1, -2, 3]),
    "nan": lambda r: r.choice([1.0, math.nan]),
    "inf": lambda r: r.choice([1.0, math.inf]),
    "tuple": lambda r: r.choice([1, (1, 2)]),
    "wide": lambda r: r.choice([1, 2**63]),
}


def _twins(cls, kind, seed, route="add_edges_from", fnx_class=None):
    r = random.Random(seed)
    n = r.choice((8, 30))
    edges = []
    for _ in range(r.choice((20, 90))):
        u, v = r.randrange(n), r.randrange(n)
        w = WEIGHTS[kind](r)
        edges.append((u, v, {} if w is None or r.random() < 0.1 else {"weight": w}))
    fg = (fnx_class or getattr(fnx, cls))()
    ng = getattr(nx, cls)()
    for g in (fg, ng):
        g.add_nodes_from(range(n))
    ng.add_edges_from(edges)
    if route == "add_edges_from":
        fg.add_edges_from(edges)
    else:
        for u, v, d in edges:
            fg.add_edge(u, v, **d)
    return fg, ng


def _typed(x):
    if isinstance(x, dict):
        return [(repr(k), _typed(v)) for k, v in x.items()]
    if isinstance(x, (list, tuple)):
        return [_typed(e) for e in x]
    return (type(x).__name__, repr(x))


def _outcome(fn):
    try:
        return _typed(fn())
    except Exception as exc:  # noqa: BLE001 - the exception type is the result
        return ("raise", type(exc).__name__)


CALLS = {
    "single_source_dijkstra_path_length": lambda m, G: m.single_source_dijkstra_path_length(G, 0),
    "single_source_bellman_ford_path_length": lambda m, G: m.single_source_bellman_ford_path_length(G, 0),
    "dijkstra_path_length": lambda m, G: m.dijkstra_path_length(G, 0, 1),
    "shortest_path_length_weight": lambda m, G: m.shortest_path_length(G, 0, weight="weight"),
    "all_pairs_dijkstra_path_length": lambda m, G: dict(m.all_pairs_dijkstra_path_length(G)),
}
UNDIRECTED_ONLY = {"single_source_dijkstra_path_length", "dijkstra_path_length", "shortest_path_length_weight", "all_pairs_dijkstra_path_length"}


@pytest.mark.parametrize("seed", range(4))
@pytest.mark.parametrize("route", ["add_edges_from", "add_edge"])
@pytest.mark.parametrize("kind", list(WEIGHTS))
@pytest.mark.parametrize("cls", ["MultiGraph", "MultiDiGraph"])
def test_multigraph_shortest_paths_match_networkx_in_order(cls, kind, route, seed):
    fg, ng = _twins(cls, kind, seed, route)
    for name, call in CALLS.items():
        if cls == "MultiDiGraph" and name in UNDIRECTED_ONLY:
            continue
        assert _outcome(lambda: call(fnx, fg)) == _outcome(lambda: call(nx, ng)), name


@pytest.mark.parametrize("cls", ["MultiGraph", "MultiDiGraph"])
def test_the_kept_collapse_follows_every_write(cls):
    fg, ng = _twins(cls, "int", 3)

    def same():
        for name, call in CALLS.items():
            if cls == "MultiDiGraph" and name in UNDIRECTED_ONLY:
                continue
            assert _outcome(lambda: call(fnx, fg)) == _outcome(lambda: call(nx, ng)), name

    same()
    same()  # the kept collapse
    u, v, k = next(iter(ng.edges(keys=True)))
    held = (fg[u][v][k], ng[u][v][k])
    for d in held:
        d["weight"] = 1
    same()
    for g in (fg, ng):
        g[u][v][k]["weight"] = 7
    same()
    attrs = {e: 2 for e in list(ng.edges(keys=True))[:10]}
    fnx.set_edge_attributes(fg, attrs, "weight")
    nx.set_edge_attributes(ng, attrs, "weight")
    same()
    for g in (fg, ng):
        g.add_edge(0, 3, weight=1)
    same()
    edge = list(ng.edges(keys=True))[5]
    for g in (fg, ng):
        g.remove_edge(*edge)
    same()
    for g in (fg, ng):
        g.add_node(99)
    same()


def test_a_subclass_takes_the_python_collapse_and_agrees():
    class Sub(fnx.MultiGraph):
        pass

    fg, ng = _twins("MultiGraph", "mixed", 2, fnx_class=Sub)
    for name, call in CALLS.items():
        assert _outcome(lambda: call(fnx, fg)) == _outcome(lambda: call(nx, ng)), name
