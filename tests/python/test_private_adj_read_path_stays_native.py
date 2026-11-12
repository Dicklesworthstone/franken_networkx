"""br-r37-c1-rgmef — the fix for private `_adj` mutability must cost nothing to READ.

`G._adj[u][v] = {...}` raises in fnx and works in networkx, because networkx's
`_adj` IS a raw dict while fnx exposes an `AdjacencyView`. This file constrains
the repair rather than the bug: it pins that whatever makes the write work must
not add a Python frame to the read path.

THE OBVIOUS FIX IS DISQUALIFIED BY MEASUREMENT. Mirroring `_PrivateNodeFacade` —
which already wraps the NodeView in Python and forwards writes for `_node` —
means wrapping the adjacency view in another object. Prototyped and measured on
the pinned ELF (attribution probes, loadavg 14.1):

    _adj[u]      unwrapped 260.3 ns   wrapped 409.4 ns   +149.1 ns (1.57x)
    _adj[u][v]   unwrapped 352.9 ns   wrapped 539.2 ns   +186.4 ns (1.53x)

That is a 50 percent regression on a READ path that networkx's own algorithms
walk directly — cluster, cycles, breadth_first_search, planarity, dominating,
regular and tournament all reach for `G._adj` — so every delegated algorithm
would pay it. The `_node` precedent is safe only because `_node` is not read in
inner loops the way `_adj` is.

AND THE FIRST VERSION OF THIS FILE PINNED THE WRONG THING, which is worth
recording because the wrong version passed review in my own head. It asserted
that `_adj.__getitem__` must be a C-level slot, on the assumption that the
260 ns baseline was native code. It is not: `type(G._adj)` is `AdjacencyView`
and its `__getitem__` is an ordinary Python function on all four classes. So the
measured facade cost was one Python frame stacked on another, and "keep it
native" was protecting something that never existed. Running the test is what
exposed that; the assumption alone would have shipped a guard against the wrong
design.

THE CONSTRAINT THAT IS ACTUALLY RIGHT, and it admits a free fix: a SUBCLASS of
the existing view inherits the identical `__getitem__` function object, so reads
are bit-for-bit the same call while `__setitem__` can be added alongside.
Verified: `PrivateAdjView.__getitem__ is AdjacencyView.__getitem__` is True.
Public `G.adj` keeps the base class and stays read-only, which is required —
networkx raises `TypeError` on `G.adj[u][v] = ...` and so must fnx.

So the rule is: `_adj`'s read methods must be THE SAME function objects as
`adj`'s. That is what this file asserts, and it survives the fix rather than
having to be deleted with it. Read alongside
`test_private_adjacency_storage_mutability.py`, which says the write must start
working; this one says it must be free.
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx

ALL = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
READ_METHODS = ["__getitem__", "__iter__", "__len__", "__contains__"]


def _graph(cls_name):
    graph = getattr(fnx, cls_name)()
    graph.add_edge("a", "b", w=1.0)
    graph.add_edge("b", "c", w=2.0)
    return graph


def _resolve(obj, name):
    for klass in type(obj).__mro__:
        if name in klass.__dict__:
            return klass.__dict__[name]
    return None


@pytest.mark.parametrize("cls_name", ALL)
@pytest.mark.parametrize("method", READ_METHODS)
def test_private_adj_read_methods_are_the_public_ones(cls_name, method):
    """THE guard: the private path must not add a frame the public one lacks.

    A facade-style fix for br-r37-c1-rgmef fails here — its `__getitem__` would
    be a new function that delegates — while a subclass-style fix passes,
    because it inherits the identical object.
    """
    graph = _graph(cls_name)
    private, public = _resolve(graph._adj, method), _resolve(graph.adj, method)
    assert public is not None, f"{cls_name}: G.adj has no {method}"
    assert private is public, (
        f"{cls_name}: G._adj.{method} is not G.adj.{method} — a wrapper was "
        "introduced on the private read path. br-r37-c1-rgmef measured that at "
        "~1.55x, and networkx's own algorithms walk G._adj directly."
    )


@pytest.mark.parametrize("cls_name", ALL)
def test_private_adj_row_read_methods_are_the_public_ones(cls_name):
    """The row is the inner loop; `_adj[u][v]` is where the cost would land."""
    graph = _graph(cls_name)
    private_row, public_row = graph._adj["a"], graph.adj["a"]
    for method in READ_METHODS:
        private, public = _resolve(private_row, method), _resolve(public_row, method)
        assert private is public, (
            f"{cls_name}: G._adj[u].{method} differs from G.adj[u].{method} — "
            "see br-r37-c1-rgmef"
        )


@pytest.mark.parametrize("cls_name", ALL)
def test_public_adjacency_stays_read_only(cls_name):
    """The other half of the constraint, and the reason a subclass is needed.

    networkx rejects `G.adj[u][v] = ...`. A fix that made the SHARED view
    writable would fix the private path by breaking the public one.
    """
    graph = _graph(cls_name)
    cell = {0: {"w": 7.0}} if cls_name.startswith("Multi") else {"w": 7.0}
    with pytest.raises(TypeError):
        graph.adj["a"]["zz"] = cell


@pytest.mark.parametrize("cls_name", ALL)
def test_private_adj_reads_agree_with_the_public_view(cls_name):
    """Keeps the identity guard from being satisfied by something fast and wrong."""
    graph = _graph(cls_name)
    assert list(graph._adj) == list(graph.adj)
    assert list(graph._adj["a"]) == list(graph.adj["a"])
    assert len(graph._adj["a"]) == len(graph.adj["a"])
    assert ("b" in graph._adj["a"]) is ("b" in graph.adj["a"])


def test_a_subclass_would_inherit_the_identical_read_methods():
    """Pins that the proposed fix shape is actually free, not assumed to be."""
    view_type = type(_graph("Graph")._adj)
    subclass = type("PrivateAdjViewProbe", (view_type,), {"__setitem__": lambda *a: None})
    for method in READ_METHODS:
        assert _resolve_type(subclass, method) is _resolve_type(view_type, method), method


def _resolve_type(klass, name):
    for base in klass.__mro__:
        if name in base.__dict__:
            return base.__dict__[name]
    return None


def test_the_node_side_precedent_is_python_and_that_is_deliberate():
    """`_node` IS a Python facade — recorded so the asymmetry reads as a choice.

    That is acceptable there because `_node` is not read in algorithm inner
    loops the way `_adj` is. If someone later finds `_node` on a hot path, this
    is where the reasoning is written down.
    """
    node_storage = _graph("Graph")._node
    assert type(node_storage).__name__ == "_PrivateNodeFacade"
    assert type(_resolve(node_storage, "__getitem__")).__name__ == "function"
