"""br-r37-c1-imddi - an ebunch that reads the graph sees every edge added before it.

networkx's add_edges_from inserts each edge before it pulls the next one, so the
dedupe-while-adding idiom works - ``M.add_edges_from((u, v) for u, v in pairs if
not M.has_edge(u, v))`` adds each pair once - and so does networkx's own
transitive_closure. fnx buffered every lazy ebunch to reach its native batches,
so a generator that read the graph saw it as it was before the call: on a
MultiGraph that idiom added every repeat as another parallel edge (55 of the 92
idiom rows below diverged).

The fix routes a lazy ebunch that can reach the graph - through a generator's
locals or closure, the globals it names, a helper function, a bound method, a
view, map/filter/itertools, functools.partial, an attribute or a small
container - to per-edge insertion, and keeps the batch for everything else. The
negative rows pin the second half: an ebunch that cannot see the graph must not
lose the batch, which a naive always-per-edge fix would.
"""

from __future__ import annotations

import functools
import itertools

import networkx as nx
import pytest

import franken_networkx as fnx

PAIRS = [(1, 2), (2, 1), (1, 2), (3, 4), (4, 3), (2, 3)]
CLASSES = ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph")


def closure_has_edge(G):
    G.add_edges_from((u, v) for u, v in PAIRS if not G.has_edge(v, u))


def bound_method(G):
    has = G.has_edge
    G.add_edges_from(e for e in PAIRS if not has(*e))


def captured_view(G):
    E = G.edges
    G.add_edges_from(e for e in PAIRS if e not in E)


def generator_function(G):
    def gen(graph, pairs):
        for u, v in pairs:
            if not graph.has_edge(u, v):
                yield u, v

    G.add_edges_from(gen(G, PAIRS))


GLOBAL_SOURCE = """
def fresh(e):
    return not G.has_edge(*e)
def run_global():
    G.add_edges_from(e for e in PAIRS if not G.has_edge(*e))
def run_helper():
    G.add_edges_from(e for e in PAIRS if fresh(e))
"""


def module_global(G):
    namespace = {"G": G, "PAIRS": PAIRS}
    exec(GLOBAL_SOURCE, namespace)
    namespace["run_global"]()


def global_helper(G):
    namespace = {"G": G, "PAIRS": PAIRS}
    exec(GLOBAL_SOURCE, namespace)
    namespace["run_helper"]()


def filter_lambda(G):
    G.add_edges_from(filter(lambda e: not G.has_edge(*e), PAIRS))


def filterfalse_lambda(G):
    G.add_edges_from(itertools.filterfalse(lambda e: G.has_edge(*e), PAIRS))


def chain_of_reader(G):
    G.add_edges_from(itertools.chain(e for e in PAIRS if not G.has_edge(*e)))


def islice_of_reader(G):
    G.add_edges_from(itertools.islice((e for e in PAIRS if not G.has_edge(*e)), 5))


class _Builder:
    def __init__(self, G):
        self.G = G

    def run(self):
        self.G.add_edges_from(e for e in PAIRS if not self.G.has_edge(*e))


def attribute_chain(G):
    _Builder(G).run()


def counter_attr(G):
    G.add_edges_from((i, i + 1, {"seen": G.number_of_edges()}) for i in range(5))


def yield_from(G):
    def inner(graph):
        for e in PAIRS:
            if not graph.has_edge(*e):
                yield e

    def outer():
        yield from inner(G)

    G.add_edges_from(outer())


def partial_predicate(G):
    def absent(graph, e):
        return not graph.has_edge(*e)

    G.add_edges_from(filter(functools.partial(absent, G), PAIRS))


def degree_reader(G):
    G.add_node(0)
    G.add_edges_from((0, v) for v in range(1, 6) if G.degree(0) < 3)


def container_holding(G):
    graphs = {"g": G}
    G.add_edges_from(e for e in PAIRS if not graphs["g"].has_edge(*e))


def attr_named_key(G):
    # ``key`` is add_edge's own parameter on a multigraph: it must stay an attribute
    G.add_edges_from((e for e in PAIRS if not G.has_edge(*e)), key=7, weight=2)


def broadcast_attr(G):
    G.add_edges_from((e for e in PAIRS if not G.has_edge(*e)), weight=2)


def triples(G):
    G.add_edges_from(
        ((u, v, {"w": G.number_of_edges()}) for u, v in PAIRS if not G.has_edge(u, v)), c=1
    )


def _raising(G, bad):
    def gen():
        for e in PAIRS[:3]:
            if not G.has_edge(*e):
                yield e
        yield bad
        yield (8, 9)

    try:
        G.add_edges_from(gen())
    except Exception as exc:  # noqa: BLE001 - the exception is part of the compared state
        G.graph["exc"] = (type(exc).__name__, str(exc))


def none_endpoint(G):
    _raising(G, (5, None))


def unhashable_endpoint(G):
    _raising(G, (5, [6]))


def bad_arity(G):
    _raising(G, (5, 6, 7, 8, 9))


def generator_raises(G):
    def gen():
        for e in PAIRS[:3]:
            if not G.has_edge(*e):
                yield e
        raise KeyError("boom")

    try:
        G.add_edges_from(gen())
    except KeyError as exc:
        G.graph["exc"] = ("KeyError", str(exc))


IDIOMS = [
    closure_has_edge, bound_method, captured_view, generator_function, module_global,
    global_helper, filter_lambda, filterfalse_lambda, chain_of_reader, islice_of_reader,
    attribute_chain, counter_attr, yield_from, partial_predicate, degree_reader,
    container_holding, attr_named_key, broadcast_attr, triples, none_endpoint,
    unhashable_endpoint, bad_arity, generator_raises,
]


def _state(G):
    if G.is_multigraph():
        edges = sorted(map(repr, G.edges(keys=True, data=True)))
    else:
        edges = sorted(map(repr, G.edges(data=True)))
    return sorted(map(repr, G.nodes)), G.graph.get("exc"), edges


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("idiom", IDIOMS, ids=lambda f: f.__name__)
def test_graph_reading_ebunch_matches_networkx(idiom, cls):
    expected, actual = getattr(nx, cls)(), getattr(fnx, cls)()
    idiom(expected)
    idiom(actual)
    assert _state(actual) == _state(expected)


def _other_graph_edges():
    H = fnx.Graph([(1, 2)])
    return (e for e in H.edges)


NOT_READING = {
    "plain genexpr": lambda: (e for e in PAIRS),
    "range genexpr": lambda: ((i, i + 1) for i in range(5)),
    "zip": lambda: zip(range(9), range(1, 10)),
    "pairwise": lambda: itertools.pairwise(range(10)),
    "map tuple": lambda: map(tuple, [[1, 2]]),
    "another graph's edges": _other_graph_edges,
    "another graph's view iterator": lambda: iter(fnx.Graph([(1, 2)]).edges),
    "list iterator": lambda: iter(PAIRS),
    "combinations": lambda: itertools.combinations(range(10), 2),
    "adjacency snapshot closure": lambda: (
        (a, b) for a in (1, 2) for b in {1: {2: {}}, 2: {1: {}}}[a]
    ),
}


@pytest.mark.parametrize("label", sorted(NOT_READING))
def test_ebunch_that_cannot_see_the_graph_keeps_the_batch(label):
    G = fnx.Graph()
    assert fnx._ebunch_reads_graph(NOT_READING[label](), G) is False


def test_container_and_view_ebunches_are_not_walked():
    G = fnx.Graph([(1, 2)])
    assert fnx._ebunch_reads_graph(G.edges, G) is False
    assert fnx._ebunch_reads_graph({(1, 2)}, G) is False
