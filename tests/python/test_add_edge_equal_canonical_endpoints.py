"""``add_edge`` must not let the second endpoint clobber the first's display key.

br-r37-c1-aeclone. Written after I broke this and the suite caught it.

The node display map is keyed by CANONICAL form, and two DIFFERENT Python objects
can share one canonical: ``12`` and ``12.0`` are one node in networkx, and any
self-loop passes the same node twice. The insert must therefore be
first-one-wins, which is what ``entry().or_insert_with()`` gave for free.

Replacing it with a conditional ``insert()`` to avoid cloning a 2000-byte
canonical on every call reintroduced last-one-wins, because ``u_was_new`` and
``v_was_new`` are BOTH computed before EITHER insert runs - so for equal
canonicals both were true and the second overwrote the first. fnx displayed
``'12'`` where networkx displays ``'12.0'``.

This file pins the semantic directly rather than relying on the adjacency-parity
test that happened to notice, so the next person to optimise this line sees the
constraint named.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]

# Pairs whose canonical forms collide, plus self-loops.
COLLIDING = [
    (12, 12.0),
    (12.0, 12),
    (0, False),
    (1, True),
    ("s", "s"),
    (7, 7),
]


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("u,v", COLLIDING, ids=repr)
def test_first_endpoint_wins_the_display_key(cls, u, v):
    got, want = getattr(fnx, cls)(), getattr(nx, cls)()
    for g in (got, want):
        g.add_edge(u, v)
    assert [repr(n) for n in got.nodes()] == [repr(n) for n in want.nodes()]
    assert [(repr(a), repr(b)) for a, b in got.edges()] == [
        (repr(a), repr(b)) for a, b in want.edges()
    ]


@pytest.mark.parametrize("cls", CLASSES)
def test_pre_existing_node_keeps_its_display_object(cls):
    """A later add_edge must not restyle a node that already exists."""
    got, want = getattr(fnx, cls)(), getattr(nx, cls)()
    for g in (got, want):
        g.add_node(12)
        g.add_edge(12.0, "other")
        g.add_edge("other", 12.0)
    assert [repr(n) for n in got.nodes()] == [repr(n) for n in want.nodes()]


@pytest.mark.parametrize("cls", CLASSES)
def test_long_key_self_loop_display(cls):
    """The shape the lever targets: 2000-char keys, endpoints equal."""
    key = "s".ljust(2000, "x")
    got, want = getattr(fnx, cls)(), getattr(nx, cls)()
    for g in (got, want):
        g.add_edge(key, key)
    assert [repr(n) for n in got.nodes()] == [repr(n) for n in want.nodes()]
    assert got.number_of_edges() == want.number_of_edges()
