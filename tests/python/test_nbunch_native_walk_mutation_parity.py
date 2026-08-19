"""The native nbunch kernel raises where networkx completes, on three classes.

br-r37-c1-hihrf. networkx lets you add an edge between two BRAND NEW nodes while
iterating ``G.edges(nbunch)``: it walks the adjacency rows of the nbunch, and a
brand-new node touches none of them. fnx's native nbunch kernel raises
RuntimeError instead.

MEASURED MAP of where fnx and networkx disagree, adding ("brand", "new") on the
first yielded edge:

    class          order   nbunch   networkx           fnx
    Graph            500        4   completes          completes
    Graph            500       16   completes          RuntimeError   <-
    Graph          20000        4   completes          completes
    Graph          20000       16   completes          completes
    DiGraph          500       16   completes          RuntimeError   <-
    DiGraph        20000       16   completes          RuntimeError   <-
    MultiGraph       500        4   completes          RuntimeError   <-
    MultiGraph     20000       16   completes          RuntimeError   <-
    MultiDiGraph     500        4   completes          RuntimeError   <-
    MultiDiGraph   20000       16   completes          RuntimeError   <-

So the faithful Python walk is effectively UNDIRECTED-GRAPH-ONLY: the multigraph
classes diverge at every size tested including nbunch=4, DiGraph diverges above
the fixed floor at any order, and only Graph is rescued - and only when
``_edges_nbunch_py_walk_limit`` (``max(8, order // 250)``) happens to cover the
nbunch.

WHY IT WAS NOT CAUGHT. The existing coverage in
test_edges_nbunch_py_walk_threshold_parity.py builds an order-20000 graph, where
that limit is 80, and tests the undirected class - the one combination the gate
does rescue. The defect lives everywhere else.

THIS ALSO PINS A PERF DECISION. The gate costs ~2x: forcing both paths at the
same size, the native kernel runs a 50-node nbunch in ~15.7us against the walk's
~32.8us, flat across a 16x range in graph order. It cannot simply be retired for
that 2x, because retiring it routes MORE calls onto the kernel that raises. The
order of work is therefore: fix the kernel, THEN drop the gate to its floor and
take the 2x. Removing these xfails is what unlocks that.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

# Cells measured to diverge today. Anything NOT listed here is asserted to match,
# so this set is a claim in both directions: shrink it when the kernel is fixed.
DIVERGENT = {
    ("Graph", 500, 16),
    ("DiGraph", 500, 16),
    ("DiGraph", 20000, 16),
    ("MultiGraph", 500, 4),
    ("MultiGraph", 500, 16),
    ("MultiGraph", 20000, 4),
    ("MultiGraph", 20000, 16),
    ("MultiDiGraph", 500, 4),
    ("MultiDiGraph", 500, 16),
    ("MultiDiGraph", 20000, 4),
    ("MultiDiGraph", 20000, 16),
}

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
ORDERS = [500, 20000]
SIZES = [4, 16]


def _iterate_and_mutate(lib, class_name, order, size):
    """Add an edge between two brand-new nodes during an nbunch iteration."""
    graph = getattr(lib, class_name)()
    graph.add_edges_from([(f"n{i}", f"n{(i + 1) % order}") for i in range(order)])
    nbunch = [f"n{i}" for i in range(size)]
    try:
        seen = 0
        for _edge in graph.edges(nbunch):
            seen += 1
            if seen == 1:
                graph.add_edge("brand", "new")
        return ("completes", seen)
    except RuntimeError:
        return ("RuntimeError",)


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("order", ORDERS)
@pytest.mark.parametrize("class_name", CLASSES)
def test_nbunch_mutation_matches_networkx(class_name, order, size):
    if (class_name, order, size) in DIVERGENT:
        pytest.xfail(
            "native nbunch kernel raises where networkx completes "
            "(br-r37-c1-hihrf); the Python walk is the faithful path and it is "
            "reached only for undirected Graph within the order-scaled limit"
        )
    expected = _iterate_and_mutate(nx, class_name, order, size)
    actual = _iterate_and_mutate(fnx, class_name, order, size)
    assert actual == expected, (
        f"{class_name}, order={order}, nbunch={size}: networkx {expected}, fnx "
        f"{actual}. An edge between two brand-new nodes touches no row the "
        f"iteration is walking, so networkx completes."
    )


def test_the_undirected_gate_is_what_rescues_graph():
    """Graph at nbunch=16 flips on graph ORDER alone - that is the gate.

    Same class, same nbunch, same mutation: divergent at order 500 where the
    limit is its floor of 8, faithful at order 20000 where the limit is 80. If
    this ever stops holding, the gate has moved and the DIVERGENT map above is
    stale.
    """
    small = _iterate_and_mutate(fnx, "Graph", 500, 16)
    large = _iterate_and_mutate(fnx, "Graph", 20000, 16)
    assert small == ("RuntimeError",), small
    assert large == _iterate_and_mutate(nx, "Graph", 20000, 16)
