"""br-r37-c1-jl8x1 — a TUPLE or FROZENSET nbunch that IS a node names that node.

``nbunch_iter`` opens with ``elif nbunch in self: return iter([nbunch])``, so a
container that is itself a node names that ONE node rather than a sequence of its
elements. Tuple node keys are ordinary networkx — ``grid_graph`` and the
cartesian products give every node a ``(row, col)`` tuple — and a frozenset is
hashable too.

fnx's ``nbunch_iter`` was correct on all four classes. The three LIST-BACKED edge
views were not: they classified their own nbunch with
``isinstance(nbunch, (list, tuple, set, frozenset))``, re-deriving the rule
without its first clause, so ``G.edges((1, 2))`` looked for nodes ``1`` and ``2``,
found neither, and returned an EMPTY LIST rather than raising. 30 cells of a
68-cell differential sweep diverged. Simple ``Graph`` was correct throughout —
its object-based ``EdgeDataView`` consults ``nbunch_iter`` instead of
re-classifying — which is what identified this as a defect in the list-backed
views rather than a house convention.

TWO SITES, and the second is why a partial fix looks like no fix at all. Even
with every classifier corrected the views still answered ``[]``, because
``_freeze_edge_view_nbunch`` re-derived the same rule a third time: it
``dict.fromkeys``'d the tuple into its elements, froze an EMPTY nbunch, and the
first refresh replaced a correctly materialised list with nothing. The raw
``list.__iter__`` contents were right the whole time. Both sites now defer to
``_nbunch_names_one_node``.

The tests below therefore read each view in the two ways that separate those
sites: straight through (the materialised answer) and after a mutation (the
rebuilt answer).
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]

TUPLE_NODE = (1, 2)
FROZEN_NODE = frozenset({7, 8})
CONTAINER_NODES = {"tuple": TUPLE_NODE, "frozenset": FROZEN_NODE}


def _build(lib, cls_name):
    graph = getattr(lib, cls_name)()
    graph.add_edge(TUPLE_NODE, "z", weight=1.0)
    graph.add_edge("y", TUPLE_NODE, weight=2.0)
    graph.add_edge(FROZEN_NODE, "z", weight=3.0)
    graph.add_edge("y", FROZEN_NODE, weight=4.0)
    graph.add_edge("y", "z", weight=5.0)
    return graph


def _norm(value):
    """A single-node nbunch makes `degree` return an INT, not pairs."""
    if isinstance(value, int):
        return value
    return sorted(value, key=repr)


def _spellings(graph, cls_name):
    table = {
        "edges": lambda nb: list(graph.edges(nb)),
        "edges(data=True)": lambda nb: list(graph.edges(nb, data=True)),
        "edges(data='weight')": lambda nb: list(graph.edges(nb, data="weight")),
        "degree": lambda nb: _norm(graph.degree(nb)),
        "subgraph": lambda nb: sorted(graph.subgraph(nb).nodes(), key=repr),
        "nbunch_iter": lambda nb: list(graph.nbunch_iter(nb)),
    }
    if cls_name in ("DiGraph", "MultiDiGraph"):
        table["out_edges"] = lambda nb: list(graph.out_edges(nb))
        table["in_edges"] = lambda nb: list(graph.in_edges(nb))
        table["out_degree"] = lambda nb: _norm(graph.out_degree(nb))
        table["in_degree"] = lambda nb: _norm(graph.in_degree(nb))
    if cls_name.startswith("Multi"):
        table["edges(keys=True)"] = lambda nb: list(graph.edges(nb, keys=True))
    return table


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("kind", sorted(CONTAINER_NODES))
def test_a_container_that_is_a_node_matches_networkx(cls_name, kind):
    """THE BUG. Fails on the unfixed arm with `[]` against networkx's edges."""
    node = CONTAINER_NODES[kind]
    gnx, gfx = _build(nx, cls_name), _build(fnx, cls_name)
    snx, sfx = _spellings(gnx, cls_name), _spellings(gfx, cls_name)
    for label in snx:
        assert sfx[label](node) == snx[label](node), (cls_name, kind, label)


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("kind", sorted(CONTAINER_NODES))
def test_the_rebuilt_answer_is_right_too(cls_name, kind):
    """The FREEZE site, separated from the classifier site.

    A view answers twice from two different places: the list materialised at
    construction, and the list its rebuild thunk produces once the graph has
    moved. The frozen nbunch feeds the second. With only the classifiers fixed
    the first read was already correct and the second still came back empty, so
    a test that reads once cannot tell the two fixes apart.
    """
    node = CONTAINER_NODES[kind]
    gnx, gfx = _build(nx, cls_name), _build(fnx, cls_name)
    view_nx, view_fx = gnx.edges(node), gfx.edges(node)
    assert list(view_fx) == list(view_nx)
    for graph in (gnx, gfx):
        graph.add_edge(node, "brand-new")
    assert list(view_fx) == list(view_nx), "rebuilt view lost the container node"
    assert len(view_fx) == len(view_nx)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_a_container_that_is_not_a_node_is_still_a_sequence(cls_name):
    """The other half of the rule, which the fix must not trade away.

    ``('y', 'z')`` is not a node here, so networkx falls past its first clause
    and treats it as a two-node sequence. A fix that routed every tuple to the
    single-node path would break this, and it is the reason the predicate asks
    ``nbunch in graph`` rather than testing the type alone.
    """
    gnx, gfx = _build(nx, cls_name), _build(fnx, cls_name)
    for nbunch in (("y", "z"), frozenset({"y", "z"}), ["y", "z"], {"y", "z"}):
        want = sorted(gnx.edges(nbunch), key=repr)
        got = sorted(gfx.edges(nbunch), key=repr)
        assert got == want, (cls_name, nbunch)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_the_predicate_is_nbunch_iters_own_question(cls_name):
    """One rule, asserted against the function that owns it."""
    graph = _build(fnx, cls_name)
    for nbunch in (
        TUPLE_NODE, FROZEN_NODE, ("y", "z"), frozenset({"y", "z"}),
        ["y"], {"y"}, "y", None, 17,
    ):
        names_one = fnx._nbunch_names_one_node(graph, nbunch)
        try:
            resolved = list(graph.nbunch_iter(nbunch))
        except fnx.NetworkXError:
            # Not a node and not a usable sequence — nbunch_iter raises, and the
            # predicate must not have claimed it was a node.
            assert names_one is False, (cls_name, nbunch)
            continue
        if names_one:
            assert resolved == [nbunch], (cls_name, nbunch, resolved)
        # The converse is not asserted: `nbunch_iter` also yields a single node
        # for a plain scalar, which this predicate deliberately answers False for
        # because no caller ever misclassified one.


@pytest.mark.parametrize("cls_name", CLASSES)
def test_an_unhashable_nbunch_never_reaches_the_membership_probe(cls_name):
    """`list` and `set` short-circuit, which is the hot path staying hot.

    Asserted as behaviour: the predicate must answer False for them WITHOUT
    consulting the graph, so a graph whose `__contains__` explodes still
    classifies a list correctly.
    """
    graph = _build(fnx, cls_name)

    class Exploding:
        def __contains__(self, item):
            raise AssertionError("membership probed for an unhashable nbunch")

    assert fnx._nbunch_names_one_node(Exploding(), ["y", "z"]) is False
    assert fnx._nbunch_names_one_node(Exploding(), {"y", "z"}) is False
    assert fnx._nbunch_is_iterable_bunch(Exploding(), ["y", "z"]) is True
    assert list(graph.edges(["y"])) == list(_build(nx, cls_name).edges(["y"]))


@pytest.mark.parametrize("cls_name", CLASSES)
def test_grid_graph_style_tuple_keys_end_to_end(cls_name):
    """The shape this actually bites: a lattice, where every node is a tuple."""
    gnx, gfx = getattr(nx, cls_name)(), getattr(fnx, cls_name)()
    for row in range(4):
        for col in range(4):
            for other in ((row + 1, col), (row, col + 1)):
                if other[0] < 4 and other[1] < 4:
                    for graph in (gnx, gfx):
                        graph.add_edge((row, col), other, weight=float(row + col))
    for node in ((0, 0), (1, 1), (3, 3)):
        assert list(gfx.edges(node)) == list(gnx.edges(node)), (cls_name, node)
        assert gfx.degree(node) == gnx.degree(node), (cls_name, node)
