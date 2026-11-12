"""`G.neighbors(n)` reads a KEY-ONLY row, and that row stays live.

br-r37-c1-3rtyk. `neighbors()` used to iterate the row `G[n]` hands out, whose
every cell is a LIVE edge attribute dict. Building one costs
`materialize_edge_py_attrs` -- four owned `String`s, a `PyDict` and two map
entries PER NEIGHBOUR -- and a `dict_keyiterator` cannot reach a value, so all
of it was built to be discarded. Measured on the cold call: ~860ns of the ~890ns
per-neighbour cost, against a Rust-side neighbour walk of ~28ns.

So PyGraph now keeps a SECOND row per node holding `{neighbour: None}`, which is
the design the multigraph classes already used (br-r37-c1-bvwam).

THE RISK THE SECOND CACHE CREATES IS STALENESS, and it is a silent-wrong-answer
risk rather than a slow one: a key row that misses a mutation reports an
adjacency the graph no longer has. Two things make that possible and each has
tests here --

  * a node can hold a key row WITHOUT an attr row (it was read through
    `neighbors()` and never through `G[n]`), so maintenance that gave up on a
    missing attr row would leave the key row untouched; and
  * the bulk edge batches skip row maintenance entirely, gated on whether a
    mirror is live -- a gate that asked only about the attr rows would run the
    batch while key rows were live.

A SNAPSHOT WOULD BE WRONG, not merely different: networkx raises RuntimeError
when the graph is mutated during `neighbors()` iteration, which happens only
because the iterator holds the very dict that mutation edits. So the rows are
maintained IN PLACE and never rebuilt behind an open iterator, and the matrix
below pins that against networkx for every mutation shape.
"""

from __future__ import annotations

import random

import networkx as nx
import pytest

import franken_networkx as fnx

MUTATIONS = [
    ("add an edge to the row", lambda g: g.add_edge("n0", "fresh")),
    ("add an unrelated edge", lambda g: g.add_edge("x", "y")),
    ("remove an edge from the row", lambda g: g.remove_edge("n0", "n3")),
    ("add an isolated node", lambda g: g.add_node("lonely")),
    ("remove another node", lambda g: g.remove_node("n5")),
    ("remove a node in the row", lambda g: g.remove_node("n2")),
    ("clear the edges", lambda g: g.clear_edges()),
    ("bulk add_edges_from", lambda g: g.add_edges_from([("n0", "b%d" % i) for i in range(10)])),
    (
        "bulk attributed add_edges_from",
        lambda g: g.add_edges_from([("n0", "c%d" % i, {"w": i}) for i in range(10)]),
    ),
    ("bulk remove_nodes_from", lambda g: g.remove_nodes_from(["n4", "n5", "n6"])),
    ("add_nodes_from", lambda g: g.add_nodes_from(["p", "q", "r"])),
]

IDS = [m[0] for m in MUTATIONS]


def _star(mod, cls_name="Graph"):
    graph = getattr(mod, cls_name)()
    for i in range(1, 7):
        graph.add_edge("n0", "n%d" % i)
    return graph


@pytest.mark.parametrize("label,mutate", MUTATIONS, ids=IDS)
@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph"])
def test_a_key_row_survives_every_mutation_shape(label, mutate, cls_name):
    """The staleness sweep: read through `neighbors()` FIRST, then mutate.

    Reading through `neighbors()` and never through `G[n]` is the state where a
    node holds a key row and no attr row, so maintenance that keyed off the attr
    row would silently skip this node.
    """
    fx, ref = _star(fnx, cls_name), _star(nx, cls_name)
    for graph in (fx, ref):
        for node in list(graph.nodes()):
            list(graph.neighbors(node))

    mutate(fx)
    mutate(ref)

    assert sorted(fx.nodes()) == sorted(ref.nodes()), label
    for node in ref.nodes():
        assert list(fx.neighbors(node)) == list(ref.neighbors(node)), (label, node)


@pytest.mark.parametrize("label,mutate", MUTATIONS, ids=IDS)
def test_both_rows_are_maintained_when_both_are_live(label, mutate):
    """THE two-cache pin: a node holding BOTH rows must see the mutation in each.

    This is the defect the second cache invites -- maintenance wired to one map
    and not the other. It cannot be caught by reading only one of them, so both
    are read here, and `G[n]` is asserted alongside `neighbors()`.
    """
    fx, ref = _star(fnx, "Graph"), _star(nx, "Graph")
    for graph in (fx, ref):
        for node in list(graph.nodes()):
            list(graph.neighbors(node))  # key row
            list(graph[node])  # attr row

    mutate(fx)
    mutate(ref)

    for node in ref.nodes():
        assert list(fx.neighbors(node)) == list(ref.neighbors(node)), (label, node)
        assert list(fx[node]) == list(ref[node]), (label, node)
        assert list(fx.neighbors(node)) == list(fx[node]), (label, node)


@pytest.mark.parametrize("label,mutate", MUTATIONS, ids=IDS)
def test_a_mutation_during_iteration_raises_exactly_when_networkx_does(label, mutate):
    """A snapshot would silently complete where networkx raises.

    CPython raises only if the dict the iterator holds is the one that changed
    size, so this is what distinguishes a live row from a rebuilt one -- and it
    is the reason the rows are edited in place rather than dropped.
    """

    def drive(graph):
        try:
            seen = 0
            for _ in graph.neighbors("n0"):
                seen += 1
                if seen == 1:
                    mutate(graph)
            return ("completed", seen)
        except RuntimeError as err:
            return ("RuntimeError", str(err))

    assert drive(_star(fnx, "Graph")) == drive(_star(nx, "Graph")), label


def test_a_key_row_is_not_stale_after_the_node_is_removed_and_re_added():
    """Removal drops the row; re-adding must not resurrect the old neighbours.

    The index twin makes this sharper than it looks: removal renumbers nodes, so
    an index entry that outlived its node would resolve to whatever node landed
    on that index -- a wrong answer built from a right one.
    """
    fx, ref = _star(fnx, "Graph"), _star(nx, "Graph")
    for graph in (fx, ref):
        list(graph.neighbors("n0"))
        graph.remove_node("n0")
        graph.add_node("n0")

    assert list(fx.neighbors("n0")) == list(ref.neighbors("n0")) == []

    for graph in (fx, ref):
        graph.add_edge("n0", "n9")
    assert list(fx.neighbors("n0")) == list(ref.neighbors("n0")) == ["n9"]

    # every OTHER node's row must have survived the renumber intact
    for node in ref.nodes():
        assert list(fx.neighbors(node)) == list(ref.neighbors(node)), node


def test_the_row_reports_the_same_keys_as_the_attr_row_for_every_key_type():
    """Same key OBJECTS, not merely equal ones (the br-r37-c1-z6uka overrides).

    The key row builds its cells with `py_adj_key`, exactly as the attr row
    does, so a graph mixing key types must iterate identically through both.
    """
    fx, ref = fnx.Graph(), nx.Graph()
    for graph in (fx, ref):
        graph.add_edge(7, 9)
        graph.add_edge(7, (1, 2))
        graph.add_edge(7, 3.5)
        graph.add_edge(7, "s")

    got = list(fx.neighbors(7))
    assert got == list(ref.neighbors(7))
    assert got == list(fx[7])
    assert [type(k) for k in got] == [type(k) for k in ref.neighbors(7)]


def test_the_iterator_is_a_dict_keyiterator_like_networkxs():
    """`G.neighbors(n)` is `iter(self._adj[n])` in networkx and nothing else."""
    fx, ref = _star(fnx, "Graph"), _star(nx, "Graph")

    assert type(fx.neighbors("n0")).__name__ == type(ref.neighbors("n0")).__name__


def test_an_absent_node_raises_networkxs_error_with_networkxs_message():
    fx, ref = _star(fnx, "Graph"), _star(nx, "Graph")

    with pytest.raises(nx.NetworkXError) as fx_err:
        list(fx.neighbors("nope"))
    with pytest.raises(nx.NetworkXError) as ref_err:
        list(ref.neighbors("nope"))

    assert str(fx_err.value) == str(ref_err.value)


def test_an_unhashable_node_raises_TypeError_rather_than_reporting_absence():
    """br-r37-c1-lvlu7: nx hashes the key first, so this is a TypeError."""
    fx, ref = _star(fnx, "Graph"), _star(nx, "Graph")

    with pytest.raises(TypeError):
        list(fx.neighbors(["unhashable"]))
    with pytest.raises(TypeError):
        list(ref.neighbors(["unhashable"]))


def test_assigned_private_storage_is_the_authority():
    """A graph carrying networkx private storage reads the ASSIGNED adjacency.

    That branch returns before any row is built, so the key row must not shadow
    it -- a cached row from before the assignment would answer the old graph.
    """
    fx, ref = _star(fnx, "Graph"), _star(nx, "Graph")
    for graph in (fx, ref):
        list(graph.neighbors("n0"))  # build a row FIRST, then override
        graph._adj = {"q": {"r": {}}, "r": {"q": {}}}
        graph._node = {"q": {}, "r": {}}

    assert list(fx.neighbors("q")) == list(ref.neighbors("q")) == ["r"]


def test_a_self_loop_appears_once_in_the_row():
    fx, ref = fnx.Graph(), nx.Graph()
    for graph in (fx, ref):
        graph.add_edge("a", "a")
        graph.add_edge("a", "b")

    assert list(fx.neighbors("a")) == list(ref.neighbors("a"))


def test_clear_is_visible_through_a_row_read_before_it():
    fx, ref = _star(fnx, "Graph"), _star(nx, "Graph")
    for graph in (fx, ref):
        list(graph.neighbors("n0"))
        graph.clear()

    assert list(fx.nodes()) == list(ref.nodes()) == []
    for graph in (fx, ref):
        graph.add_edge("n0", "z")
    assert list(fx.neighbors("n0")) == list(ref.neighbors("n0")) == ["z"]


@pytest.mark.parametrize("seed", range(12))
def test_randomised_mutation_sequences_agree_with_networkx(seed):
    """The sweep that found nothing by construction and everything by accident.

    Reads are interleaved as OPERATIONS, so a key row is created at arbitrary
    points and then subjected to whatever the sequence does next -- including
    the bulk batches, which is where a liveness gate that asked only about the
    attr rows would let the row rot.
    """
    rng = random.Random(seed)
    fx, ref = fnx.Graph(), nx.Graph()
    names = [str(i) for i in range(12)] + [7, 9, (1, 2), 3.5]

    def key():
        return rng.choice(names)

    for _step in range(120):
        op = rng.randrange(9)
        if op == 0:
            a, b = key(), key()
            fx.add_edge(a, b)
            ref.add_edge(a, b)
        elif op == 1:
            a, b = key(), key()
            if ref.has_edge(a, b):
                fx.remove_edge(a, b)
                ref.remove_edge(a, b)
        elif op == 2:
            a = key()
            if ref.has_node(a):
                fx.remove_node(a)
                ref.remove_node(a)
        elif op == 3:
            batch = [(key(), key()) for _ in range(rng.randrange(8, 13))]
            fx.add_edges_from(batch)
            ref.add_edges_from(batch)
        elif op == 4:
            batch = [(key(), key(), {"w": 1}) for _ in range(rng.randrange(8, 12))]
            fx.add_edges_from(batch)
            ref.add_edges_from(batch)
        elif op == 5:  # a READ, which is what puts a key row in play
            a = key()
            if ref.has_node(a):
                list(fx.neighbors(a))
                list(ref.neighbors(a))
        elif op == 6:
            a = key()
            if ref.has_node(a):
                list(fx[a])
                list(ref[a])
        elif op == 7:
            present = [x for x in (key(), key()) if ref.has_node(x)]
            fx.remove_nodes_from(present)
            ref.remove_nodes_from(present)
        else:
            a = key()
            fx.add_node(a)
            ref.add_node(a)

        assert sorted(map(str, fx.nodes())) == sorted(map(str, ref.nodes()))
        for node in ref.nodes():
            assert list(fx.neighbors(node)) == list(ref.neighbors(node)), node
            assert list(fx[node]) == list(ref[node]), node
