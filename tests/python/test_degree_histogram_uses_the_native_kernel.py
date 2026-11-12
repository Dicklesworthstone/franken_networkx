"""`degree_histogram` answers from the native kernel, and only where it may.

br-r37-c1-deghistdead. The kernel existed in `fnx-algorithms`, was exported by
the binding, and was imported by the shim as `_raw_degree_histogram` - and was
never called. The Python body rebuilt networkx's own algorithm instead (a
`Counter` over N `(node, degree)` tuples), so the port paid nx's cost to produce
nx's answer: 124.2us against networkx's 158.3us on a 1200-node/4800-edge Graph.

IT WAS NEVER CALLABLE AS A DROP-IN, which is the part worth keeping. Wiring it
up cost 53 test failures, because it counted the ADJACENCY ROW LENGTH and that is
not networkx's degree wherever an edge contributes more than one:

    Graph a-a, a-b        nx [0,1,0,1]   kernel [0,1,1]     a self-loop is 2
    MultiGraph a-b twice  nx [0,1,1,1]   kernel [0,2,1]     multiplicity
    DiGraph a->b, b->a    nx [0,0,2]     kernel [0,2]       reciprocal pair
    MultiDiGraph a-b x2   nx [0,0,2]     kernel [0,2]

The self-loop half is now fixed in the kernel. The other three are properties of
the UNDIRECTED SIMPLE projection the binding reads, and are not recoverable from
it, so the binding answers `None` for those classes and the Python body keeps
them. On a release build the plain-Graph path is 5.7us against networkx's 154.0us.

SO THIS FILE IS MOSTLY ABOUT THE GRAPHS THAT MUST NOT TAKE THE FAST PATH: the
three declined classes, a subgraph VIEW (it subclasses the native class and its
Rust base is EMPTY - the kernel returned `[]`, "every node is isolated", where
networkx returns a real histogram), a graph carrying assigned private storage,
and a foreign networkx graph. A test that only checked the four concrete classes
on simple fixtures would pass while every one of those was wrong.
"""

from __future__ import annotations

import random

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _pair(cls_name="Graph", nodes=60, edges=140, seed=7):
    graphs = []
    for mod in (fnx, nx):
        rng = random.Random(seed)
        graph = getattr(mod, cls_name)()
        names = [str(i) for i in range(nodes)]
        graph.add_nodes_from(names)
        seen = set()
        while len(seen) < edges:
            a, b = rng.randrange(nodes), rng.randrange(nodes)
            if a == b or (a, b) in seen or (b, a) in seen:
                continue
            seen.add((a, b))
            graph.add_edge(names[a], names[b])
        graphs.append(graph)
    return graphs[0], graphs[1]


@pytest.mark.parametrize("cls_name", CLASSES)
def test_matches_networkx_on_every_class(cls_name):
    fx, ref = _pair(cls_name)

    assert fnx.degree_histogram(fx) == nx.degree_histogram(ref)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_an_empty_graph_and_an_isolated_node(cls_name):
    """`max(counts)` on an empty Counter is the classic edge of this function."""
    fx, ref = getattr(fnx, cls_name)(), getattr(nx, cls_name)()
    assert fnx.degree_histogram(fx) == nx.degree_histogram(ref) == []

    fx.add_node("lonely")
    ref.add_node("lonely")
    assert fnx.degree_histogram(fx) == nx.degree_histogram(ref) == [1]


@pytest.mark.parametrize("cls_name", CLASSES)
def test_a_view_does_not_answer_from_the_rust_store(cls_name):
    """THE case the guard exists for - measured wrong before it.

    A view subclasses the native class, so the kernel accepts it happily and its
    Rust base is empty. Without the type-identity guard this returned `[]` where
    networkx returns a real histogram, which reads as "every node is isolated".
    """
    fx, ref = _pair(cls_name)
    keep = [str(i) for i in range(12)]

    got = fnx.degree_histogram(fx.subgraph(keep))
    want = nx.degree_histogram(ref.subgraph(keep))

    assert got == want
    assert any(want), "fixture is degenerate: an all-zero histogram cannot catch []"


@pytest.mark.parametrize("cls_name", CLASSES)
def test_assigned_private_storage_is_the_authority(cls_name):
    """A NetworkX utility can assign `_node`; the mapping wins over the store."""
    fx, ref = _pair(cls_name)
    for graph in (fx, ref):
        graph._node = {"q1": {}, "q2": {}}

    assert fnx.degree_histogram(fx) == nx.degree_histogram(ref)


def test_a_networkx_graph_still_works_through_the_python_body():
    """The kernel raises TypeError on a foreign graph; the shim must not."""
    _fx, ref = _pair()

    assert fnx.degree_histogram(ref) == nx.degree_histogram(ref)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_mutations_are_visible(cls_name):
    """A kernel reading a stale store would show up here and nowhere else."""
    fx, ref = _pair(cls_name)
    before = fnx.degree_histogram(fx)

    for graph in (fx, ref):
        graph.add_edge("brand", "new")

    assert fnx.degree_histogram(fx) == nx.degree_histogram(ref)
    assert fnx.degree_histogram(fx) != before

    for graph in (fx, ref):
        graph.remove_node("brand")
    assert fnx.degree_histogram(fx) == nx.degree_histogram(ref)


def test_the_native_kernel_is_actually_reached_for_a_plain_graph():
    """Pins the wiring, not just the answer.

    The defect was a correct answer computed the slow way, which no value
    assertion can see: if the fast path stops being taken the answers stay right
    and the speedup quietly goes away.
    """
    fx, _ref = _pair()
    from franken_networkx import _fnx

    assert _fnx.degree_histogram(fx) is not None
    assert fnx.degree_histogram(fx) == _fnx.degree_histogram(fx)


@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiGraph", "MultiDiGraph"])
def test_the_kernel_declines_the_classes_it_cannot_serve(cls_name):
    """`None`, not a guess - the contract that makes the fast path safe.

    The kernel reads an UNDIRECTED SIMPLE projection, which is not networkx's
    degree on these three: a reciprocal DiGraph pair is degree 2 per node and
    collapses to 1, and parallel edges count with multiplicity. Wiring it as a
    drop-in cost 53 test failures. Declining is what keeps the Python body in
    charge where it must be.
    """
    from franken_networkx import _fnx

    fx, _ref = _pair(cls_name)

    assert _fnx.degree_histogram(fx) is None


def test_a_view_is_declined_rather_than_answered_emptily():
    """A view subclasses the native class; its Rust base is EMPTY.

    Before the binding was restricted this returned `[]` - "every node is
    isolated" - for a view whose real histogram is non-trivial
    (br-r37-c1-kum9v).
    """
    from franken_networkx import _fnx

    fx, ref = _pair()
    keep = [str(i) for i in range(12)]
    view, ref_view = fx.subgraph(keep), ref.subgraph(keep)

    assert fnx.degree_histogram(view) == nx.degree_histogram(ref_view)
    assert any(nx.degree_histogram(ref_view))


SELF_LOOP_AND_PARALLEL = [
    ("self-loop Graph", "Graph", [("a", "a"), ("a", "b")]),
    ("self-loop DiGraph", "DiGraph", [("a", "a"), ("a", "b")]),
    ("self-loop MultiGraph", "MultiGraph", [("a", "a"), ("a", "b")]),
    ("reciprocal DiGraph", "DiGraph", [("a", "b"), ("b", "a")]),
    ("parallel MultiGraph", "MultiGraph", [("a", "b"), ("a", "b"), ("b", "c")]),
    ("parallel MultiDiGraph", "MultiDiGraph", [("a", "b"), ("a", "b")]),
]


@pytest.mark.parametrize(
    "label,cls_name,edges",
    SELF_LOOP_AND_PARALLEL,
    ids=[c[0] for c in SELF_LOOP_AND_PARALLEL],
)
def test_the_shapes_where_degree_is_not_the_neighbour_count(label, cls_name, edges):
    """Every shape that made the drop-in wrong, asserted one by one.

    A self-loop is degree TWO and parallel edges count with multiplicity. The
    kernel counted adjacency-row length, so each of these produced a plausible
    histogram that was simply not networkx's.
    """
    fx, ref = getattr(fnx, cls_name)(), getattr(nx, cls_name)()
    for u, v in edges:
        fx.add_edge(u, v)
        ref.add_edge(u, v)

    assert fnx.degree_histogram(fx) == nx.degree_histogram(ref), label
