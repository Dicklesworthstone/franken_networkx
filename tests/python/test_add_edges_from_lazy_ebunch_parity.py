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


# br-r37-c1-ow0ie - add_nodes_from buffers a graph, a view or a generator to reach
# the native node batches (they take a concrete list), under the same rule: an
# argument that can read the graph it fills goes node by node, and so does a
# view of that graph - its edges as nodes raise in networkx's live iteration.
# The batches now take new nodes into a graph that has some; a node the graph
# already has goes node by node, since its dict may be held.


def _node_source(m, cls):
    H = getattr(m, cls)()
    H.add_edges_from([(10, 11), (11, 12), ("a", 12)])
    H.nodes[11]["w"] = 3
    for i in range(20, 32):
        H.add_node(i, k=i)
    return H


def _raise_at(items, at):
    for i, item in enumerate(items):
        if i == at:
            raise KeyError("boom")
        yield item


NODE_ARGUMENTS = {
    "another graph": lambda G, H: H,
    "its nodes": lambda G, H: H.nodes,
    "its nodes(data=True)": lambda G, H: H.nodes(data=True),
    "its nodes.items()": lambda G, H: H.nodes.items(),
    "its nodes(data='w')": lambda G, H: H.nodes(data="w"),
    "pairs genexpr": lambda G, H: ((n, d) for n, d in H.nodes(data=True)),
    "map to str": lambda G, H: map(str, range(12)),
    "range not from 0": lambda G, H: range(5, 40),
    "set of str": lambda G, H: {f"s{i}" for i in range(12)},
    "dict": lambda G, H: {f"d{i}": i for i in range(12)},
    "str": lambda G, H: "abcdefghijk",
    "this graph": lambda G, H: G,
    "this graph's nodes(data=True)": lambda G, H: G.nodes(data=True),
    "this graph's edges": lambda G, H: G.edges,
    "reads len while adding": lambda G, H: (len(G) + i for i in range(12)),
    "reads membership while adding": lambda G, H: (
        i % 4 + 100 for i in range(12) if i % 4 + 100 not in G
    ),
    "raises after nine": lambda G, H: _raise_at(list(range(100, 130)), 9),
    "raises after nine pairs": lambda G, H: _raise_at([(i, {"z": i}) for i in range(100, 130)], 9),
    "bad 3-tuple": lambda G, H: iter([(i, {"q": 1}) for i in range(100, 110)] + [(1, 2, {}), 200]),
    "unhashable": lambda G, H: iter([*range(100, 110), [1], 200]),
    "None": lambda G, H: iter([*range(100, 110), None, 200]),
    "non-str attribute keys": lambda G, H: iter([(i, {2: "x", "y": 1}) for i in range(10)]),
    "add_node parameter names": lambda G, H: iter(
        [(i, {"node_for_adding": i, "self": 0}) for i in range(10)]
    ),
    "not iterable": lambda G, H: 5,
    "list of new nodes": lambda G, H: [(f"new{i}", {"i": i}) for i in range(10)] + ["plain"],
    "list with a node the graph has": lambda G, H: [(i, {"i": i}) for i in range(8)] + [(1, {"c": 9})],
    "generator of new nodes": lambda G, H: ((f"new{i}", {"i": i, "j": 0}) for i in range(30)),
    "generator repeating a node": lambda G, H: (
        (i % 11, {"round": i // 11}) for i in range(30)
    ),
}


def _nodes_state(G):
    return sorted(map(repr, G.nodes(data=True))), list(map(repr, G))


def _add_nodes_outcome(m, cls, label, fresh):
    G = getattr(m, cls)()
    if not fresh:
        G.add_edges_from([(0, 1), (1, 2)])
        G.nodes[1]["c"] = 5
    try:
        G.add_nodes_from(NODE_ARGUMENTS[label](G, _node_source(m, cls)))
    except Exception as exc:  # noqa: BLE001 - the exception is part of the compared state
        return _nodes_state(G), (type(exc).__name__, exc.args)
    return _nodes_state(G), None


@pytest.mark.parametrize("fresh", [True, False], ids=["empty", "non-empty"])
@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("label", list(NODE_ARGUMENTS))
def test_add_nodes_from_argument_matches_networkx(label, cls, fresh):
    assert _add_nodes_outcome(fnx, cls, label, fresh) == _add_nodes_outcome(nx, cls, label, fresh)


@pytest.mark.parametrize("cls", CLASSES)
def test_add_nodes_from_stops_pulling_at_the_element_networkx_rejects(cls):
    left = {}
    for m in (fnx, nx):
        G = getattr(m, cls)()
        items = iter([(i, {"q": 1}) for i in range(100, 110)] + [(1, 2, {}), 200, 201])
        with pytest.raises(ValueError):
            G.add_nodes_from(items)
        left[m] = (list(items), sorted(G))
    assert left[fnx] == left[nx]
    assert left[fnx][0] == [200, 201]


def _add_node_calls(G, argument):
    calls = 0

    def count(frame, event, arg):
        nonlocal calls
        if event == "call" and frame.f_code.co_name == "add_node" and frame.f_code.co_filename == fnx.__file__:
            calls += 1

    import sys

    sys.setprofile(count)
    try:
        G.add_nodes_from(argument)
    finally:
        sys.setprofile(None)
    return calls


def _seeded(m, cls, fresh):
    G = getattr(m, cls)()
    if not fresh:
        G.add_edges_from([("x", "y"), ("y", "z")])
        G.nodes["x"]["c"] = 1
    return G


@pytest.mark.parametrize("fresh", [True, False], ids=["empty", "non-empty"])
@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize(
    "shape",
    ["list", "graph", "nodes", "nodes(data=True)", "pairs genexpr", "str genexpr"],
)
def test_new_nodes_take_the_batch(cls, shape, fresh):
    H = getattr(fnx, cls)()
    for i in range(40):
        H.add_node(f"n{i}", k=i)
        H.add_node(i)
    make = {
        "list": lambda: list(H.nodes(data=True)),
        "graph": lambda: H,
        "nodes": lambda: H.nodes,
        "nodes(data=True)": lambda: H.nodes(data=True),
        "pairs genexpr": lambda: ((n, d) for n, d in H.nodes(data=True)),
        "str genexpr": lambda: (f"s{i}" for i in range(40)),
    }[shape]
    G = _seeded(fnx, cls, fresh)
    # A one-shot iterator's first batch-minimum go node by node; the rest is one batch.
    head = fnx._NODE_BATCH_MIN if shape.endswith("genexpr") else 0
    assert _add_node_calls(G, make()) == head
    expected = _seeded(nx, cls, fresh)
    expected.add_nodes_from(list(make()))
    assert _nodes_state(G) == _nodes_state(expected)


@pytest.mark.parametrize("cls", CLASSES)
def test_a_node_the_graph_has_merges_into_the_held_dict(cls):
    for m in (fnx, nx):
        G = _seeded(m, cls, fresh=False)
        held = G.nodes["x"]
        G.add_nodes_from([(f"new{i}", {"i": i}) for i in range(10)] + [("x", {"late": 2})])
        assert held == {"c": 1, "late": 2}
        assert G.nodes["x"] is held
        assert list(G) == ["x", "y", "z", *(f"new{i}" for i in range(10))]


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("start", [20, 15], ids=["new", "overlapping"])
def test_nodes_after_a_range_match_networkx(cls, start):
    states = []
    for m in (fnx, nx):
        G = getattr(m, cls)()
        G.add_nodes_from(range(20))
        G.add_edge(3, 4)
        G.add_nodes_from([(i, {"a": i}) for i in range(start, 40)] + ["s", 2.5])
        G.add_nodes_from((f"g{i}", {"b": i}) for i in range(12))
        states.append((_nodes_state(G), [type(n).__name__ for n in G]))
    assert states[0] == states[1]


@pytest.mark.parametrize("cls", CLASSES)
def test_new_nodes_invalidate_an_open_edge_iterator(cls):
    outcome = {}
    for m in (fnx, nx):
        G = _seeded(m, cls, fresh=False)
        edges = iter(G.edges(data=True))
        next(edges)
        G.add_nodes_from([f"new{i}" for i in range(10)])
        try:
            next(edges)
        except RuntimeError as exc:
            outcome[m] = ("RuntimeError", str(exc))
        else:
            outcome[m] = None
    assert outcome[fnx] == outcome[nx]


def test_graph_reading_node_argument_goes_node_by_node():
    G, expected = fnx.Graph(), nx.Graph()
    assert _add_node_calls(G, (len(G) + i for i in range(12))) == 12
    expected.add_nodes_from(len(expected) + i for i in range(12))
    assert list(G) == list(expected) == list(range(0, 24, 2))
    G = fnx.Graph([(f"a{i}", f"b{i}") for i in range(10)])
    assert _add_node_calls(G, G.nodes(data=True)) == 20
    assert fnx._view_holds_graph(G.edges, G) is True
    assert fnx._view_holds_graph(G.nodes(data=True), G) is True
    assert fnx._view_holds_graph(G.nodes.items(), G) is True
    assert fnx._view_holds_graph(G.degree, G) is True
    H = fnx.Graph([(0, 1)])
    assert fnx._view_holds_graph(H.nodes(data=True), G) is False
    assert fnx._view_holds_graph(H.edges, G) is False
    assert fnx._view_holds_graph(H, G) is False
