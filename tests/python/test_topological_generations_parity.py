"""Post-w7nn3 delegation re-audit find: topological_generations
lexicographically sorted each generation (string order put "10" before
"2") instead of nx's node-iteration order (gen 0) / zero-reach order
(later gens), and displayed members as node-map objects instead of the
zeroing parent's succ-row object (discovery-object class).
"""

import random

import networkx as nx
import pytest

import franken_networkx as fnx


def _rr(gens):
    return [[repr(n) for n in gen] for gen in gens]


def test_no_lexicographic_string_sort():
    gn, gf = nx.DiGraph(), fnx.DiGraph()
    for g in (gn, gf):
        for i in range(14):
            g.add_edge("root", i)
    assert _rr(fnx.topological_generations(gf)) == _rr(nx.topological_generations(gn))


def test_zero_reach_order_within_generation():
    gn, gf = nx.DiGraph(), fnx.DiGraph()
    for g in (gn, gf):
        for e in [(0, 2), (1, 2), (0, 1), (2, 4), (2, 3), (3, 5), (4, 5), (0, 5)]:
            g.add_edge(*e)
    assert _rr(fnx.topological_generations(gf)) == _rr(nx.topological_generations(gn))


def test_multigraph_parallel_edge_decrement():
    gn, gf = nx.MultiDiGraph(), fnx.MultiDiGraph()
    for g in (gn, gf):
        g.add_edge(0, 1)
        g.add_edge(0, 1)
        g.add_edge(1, 2)
        g.add_edge(0, 2)
    assert _rr(fnx.topological_generations(gf)) == _rr(nx.topological_generations(gn))


def test_mixed_key_zeroing_parent_row_objects():
    gn, gf = nx.DiGraph(), fnx.DiGraph()
    for g in (gn, gf):
        g.add_node(28)
        g.add_edge(7, 28.0)
        g.add_edge(28.0, 5)
    assert _rr(fnx.topological_generations(gf)) == _rr(nx.topological_generations(gn))


def test_random_dag_corpus():
    rnd = random.Random(31)
    for trial in range(20):
        n = rnd.randrange(4, 16)
        gn, gf = nx.DiGraph(), fnx.DiGraph()
        for g in (gn, gf):
            g.add_nodes_from(range(n))
        for _ in range(rnd.randrange(3, 30)):
            u, v = rnd.randrange(n), rnd.randrange(n)
            if u < v:
                gn.add_edge(u, v)
                gf.add_edge(u, v)
        assert _rr(fnx.topological_generations(gf)) == _rr(
            nx.topological_generations(gn)
        ), trial


def test_cycle_raises_unfeasible():
    gf = fnx.DiGraph([(1, 2), (2, 1)])
    with pytest.raises(fnx.NetworkXUnfeasible):
        list(fnx.topological_generations(gf))


# nro4w.11: networkx processes each generation (each node, for the
# lexicographical sort) on the LIVE graph just before yielding it. A caller that
# mutates the graph mid-iteration gets RuntimeError or NetworkXUnfeasible at
# exactly the point networkx notices, and a cyclic graph yields its acyclic
# prefix before NetworkXUnfeasible.

import inspect

SORTS = ("topological_generations", "topological_sort", "lexicographical_topological_sort")


def _drive(mod, fn, graph, mutations):
    """Iterate ``fn(graph)``, applying ``mutations[i]`` after the i-th yield."""
    out = []
    try:
        for i, item in enumerate(getattr(mod, fn)(graph)):
            out.append([repr(n) for n in item] if isinstance(item, list) else repr(item))
            for mutate in mutations.get(i, ()):
                mutate(graph)
        return out, None, None
    except Exception as err:  # the exception is part of the contract under test
        return out, type(err).__name__, str(err)


def _pair(cls, edges, nodes=()):
    gn, gf = getattr(nx, cls)(), getattr(fnx, cls)()
    for g in (gn, gf):
        g.add_nodes_from(nodes)
        g.add_edges_from(edges)
    return gn, gf


@pytest.mark.parametrize("fn", ["topological_sort", "lexicographical_topological_sort"])
@pytest.mark.parametrize(
    "mutate, expected",
    [
        # networkx's test_dag.py::test_topological_sort6, after the first yield.
        (lambda G, x: G.add_edge(5 - x, 5), ([1, 2, 3], "RuntimeError")),
        (lambda G, x: G.remove_node(4), ([1, 2, 3], "NetworkXUnfeasible")),
        (lambda G, x: G.remove_node(2), ([1], "RuntimeError")),
    ],
)
def test_networkx_mutation_scenarios(fn, mutate, expected):
    G = fnx.DiGraph([(1, 2), (2, 3), (3, 4)])
    seen = []
    with pytest.raises(Exception) as info:
        for x in getattr(fnx, fn)(G):
            seen.append(x)
            if len(seen) == 1:
                mutate(G, x)
    assert (seen, type(info.value).__name__) == expected


@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("fn", SORTS)
def test_cyclic_graph_yields_the_acyclic_prefix_first(cls, fn):
    gn, gf = _pair(cls, [(0, 1), (1, 2), (2, 1), (0, 3), (3, 4), (5, 5)], nodes=[6])
    expected = _drive(nx, fn, gn, {})
    assert expected[1] == "NetworkXUnfeasible" and expected[0]
    assert _drive(fnx, fn, gf, {}) == expected


@pytest.mark.parametrize("fn", SORTS)
def test_the_sorts_are_generator_functions(fn):
    assert inspect.isgeneratorfunction(getattr(fnx, fn)) == inspect.isgeneratorfunction(
        getattr(nx, fn)
    )


class _SubDiGraph(fnx.DiGraph):
    pass


def _random_mutation(rnd, multigraph):
    kind = rnd.choice(
        ["edge", "edge", "new_child", "new_parent", "remove_node", "remove_edge",
         "add_node", "edges", "clear_edges"] + (["parallel", "parallel"] if multigraph else [])
    )
    a, b = rnd.randrange(12), rnd.randrange(12)

    def mutate(G):
        nodes = list(G)
        if kind in ("edge", "parallel") and nodes:
            u, v = nodes[a % len(nodes)], nodes[b % len(nodes)]
            G.add_edge(u, v)
        elif kind == "new_child" and nodes:
            G.add_edge(nodes[a % len(nodes)], 100 + b)
        elif kind == "new_parent" and nodes:
            G.add_edge(100 + b, nodes[a % len(nodes)])
        elif kind == "remove_node" and nodes:
            G.remove_node(nodes[a % len(nodes)])
        elif kind == "remove_edge":
            edges = list(G.edges())
            if edges:
                G.remove_edge(*edges[a % len(edges)])
        elif kind == "add_node":
            G.add_node(200 + a)
        elif kind == "edges" and nodes:
            G.add_edges_from([(nodes[a % len(nodes)], nodes[(a + b) % len(nodes)]), (nodes[b % len(nodes)], 300)])
        elif kind == "clear_edges":
            G.clear_edges()

    return mutate


@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
def test_random_mutation_during_iteration_matches_networkx(cls):
    rnd = random.Random(20260924)
    multigraph = cls == "MultiDiGraph"
    for trial in range(300):
        n = rnd.randrange(1, 10)
        edges = []
        for _ in range(rnd.randrange(0, 18)):
            u, v = rnd.randrange(n), rnd.randrange(n)
            if u < v or rnd.random() < 0.08:  # mostly acyclic, sometimes not
                edges.append((u, v))
        schedule = {}
        for _ in range(rnd.randrange(0, 3)):
            schedule.setdefault(rnd.randrange(0, n + 1), []).append(_random_mutation(rnd, multigraph))
        for fn in SORTS:
            gn, gf = _pair(cls, edges, nodes=range(n))
            expected = _drive(nx, fn, gn, schedule)
            assert _drive(fnx, fn, gf, schedule) == expected, (trial, fn, edges, expected)
            if cls == "DiGraph":
                sub = _SubDiGraph()
                sub.add_nodes_from(range(n))
                sub.add_edges_from(edges)
                assert _drive(fnx, fn, sub, schedule) == expected, ("subclass", trial, fn)
                nx_input = nx.DiGraph()
                nx_input.add_nodes_from(range(n))
                nx_input.add_edges_from(edges)
                assert _drive(fnx, fn, nx_input, schedule) == expected, ("nx input", trial, fn)
