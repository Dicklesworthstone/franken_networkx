"""br-r37-c1-vaayu — skipping the shadow installer on classes that shadow nothing.

`_install_private_method_shadows` restores mapping-aware dispatch on instances
whose NetworkX private stores have been assigned. br-r37-c1-8itxk memoised the
per-(class, name) eligibility inside it, which removed the MRO walks but not the
calls: a reverse view assigns three private overrides at construction and each
one walked the whole body and called `install()` four times — twelve calls per
`reverse(copy=False)` that could never install anything.

They could never install anything because ELIGIBILITY IS A PROPERTY OF THE CLASS,
and a reverse view's class overrides those methods in Python, so none of them is
the raw PyO3 descriptor the installer is permitted to shadow. Measured over the
seven names the installer handles:

    reverse-view class    NONE eligible
    DiGraph               all 7
    Graph                 5

    reverse(copy=False)   DiGraph 0.482x -> 0.579x, MultiDiGraph 0.491x -> 0.582x

The danger of a class-level short-circuit is over-reach: skipping the installer
for a class that DOES need it would silently restore raw dispatch on a graph
whose private store was reassigned, which is a correctness bug that no timing
would reveal. So these tests are mostly about the classes that must NOT be
skipped.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _build(lib, cls_name, order=40):
    graph = getattr(lib, cls_name)()
    for i in range(order):
        graph.add_edge(f"n{i}", f"n{(i * 7 + 3) % order}")
    return graph


def test_the_predicate_agrees_with_a_direct_eligibility_scan():
    """The memo must answer exactly what the per-name check would."""
    names = [
        ("has_node", fnx._RAW_HAS_NODE_METHODS),
        ("number_of_nodes", fnx._RAW_NUMBER_OF_NODES_METHODS),
        ("order", fnx._RAW_NUMBER_OF_NODES_METHODS),
        ("has_edge", fnx._RAW_HAS_EDGE_METHODS),
        ("get_edge_data", fnx._RAW_GET_EDGE_DATA_METHODS),
        ("neighbors", fnx._RAW_DIGRAPH_NEIGHBOR_METHODS),
        ("successors", fnx._RAW_DIGRAPH_NEIGHBOR_METHODS),
    ]

    def scan(cls):
        for name, raws in names:
            class_method = next(
                (b.__dict__[name] for b in cls.__mro__ if name in b.__dict__), None
            )
            if any(class_method is raw for raw in raws):
                return False
        return True

    subjects = [getattr(fnx, c) for c in CLASSES]
    subjects.append(type(_build(fnx, "DiGraph").reverse(copy=False)))
    subjects.append(type(_build(fnx, "Graph").subgraph(["n0", "n1"])))
    for cls in subjects:
        assert fnx._class_shadows_nothing(cls) == scan(cls), cls


@pytest.mark.parametrize("cls_name", CLASSES)
def test_concrete_classes_are_NOT_short_circuited(cls_name):
    """The classes that need the installer must still reach it.

    If this ever flips to True the short-circuit has swallowed a class that
    genuinely shadows, and assigned-private-storage dispatch breaks silently.
    """
    assert not fnx._class_shadows_nothing(getattr(fnx, cls_name))


@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
def test_reverse_view_class_is_short_circuited(cls_name):
    """Non-vacuity: the lever must actually apply to the class it was written for."""
    view = _build(fnx, cls_name).reverse(copy=False)
    assert fnx._class_shadows_nothing(type(view))


@pytest.mark.parametrize("cls_name", CLASSES)
def test_assigned_private_storage_still_gets_mapping_aware_dispatch(cls_name):
    """The behaviour the installer exists for, asserted end to end.

    networkx utilities replace G._node / G._adj with plain mappings. After that
    the primitives must answer from the mapping, not from the Rust store.
    """
    graph = _build(fnx, cls_name)
    graph._node = {"only": {}}
    assert graph.has_node("only")
    assert not graph.has_node("n0")
    assert graph.number_of_nodes() == 1
    assert graph.order() == 1


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("store", ["_adj", "_succ"])
def test_assigned_adjacency_edge_membership_matches_networkx(cls_name, store):
    """Differential, not a guess.

    An earlier draft asserted has_edge("u","v") was True after assigning _adj.
    It is not, on either library — a directed graph reads `_succ`, and the
    undirected inner shape differs — so the assertion was about my fixture
    rather than about fnx. What matters is that fnx answers whatever networkx
    answers once the private store is assigned, which is exactly the dispatch
    the installer exists to restore.
    """
    results = []
    for lib in (nx, fnx):
        graph = _build(lib, cls_name)
        if store == "_succ" and not graph.is_directed():
            pytest.skip("undirected graphs have no _succ")
        inner = {0: {}} if graph.is_multigraph() else {}
        setattr(graph, store, {"u": {"v": inner}, "v": {"u": inner}})
        row = []
        for call in (
            lambda g: g.has_edge("u", "v"),
            lambda g: g.has_edge("n0", "n1"),
            lambda g: g.get_edge_data("u", "v"),
        ):
            try:
                row.append(("ok", call(graph)))
            except Exception as exc:  # noqa: BLE001
                row.append((type(exc).__name__,))
        results.append(row)
    want, got = results
    # br-r37-c1-yyfmb: the EDGE half of this mechanism does not read the
    # assigned mapping, so fnx answers False/None where networkx answers
    # True/{}. Verified PRE-EXISTING against an unmodified HEAD with the
    # br-r37-c1-vaayu change reverted, so it is not this bead's doing. Recorded
    # as the current state rather than asserted away; this pin fails -- and
    # should be replaced by `assert got == want` -- when yyfmb lands.
    assert got[1] == want[1], "membership for an absent edge must still agree"
    if got == want:
        pytest.fail(
            "br-r37-c1-yyfmb appears FIXED: assigned-adjacency edge dispatch now "
            "matches networkx. Replace this pin with a direct equality assertion."
        )
    assert got[0] == ("ok", False) and got[2] == ("ok", None), (
        f"br-r37-c1-yyfmb residue CHANGED shape: {got!r} (was False/None)"
    )


@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
def test_reverse_view_behaviour_matches_networkx(cls_name):
    """The short-circuited path must still produce networkx's reverse view."""
    gnx, gfx = _build(nx, cls_name), _build(fnx, cls_name)
    rnx, rfx = gnx.reverse(copy=False), gfx.reverse(copy=False)
    assert sorted(rfx.edges()) == sorted(rnx.edges())
    assert sorted(rfx.nodes()) == sorted(rnx.nodes())
    for node in ("n0", "n5"):
        assert sorted(rfx.successors(node)) == sorted(rnx.successors(node))
        assert sorted(rfx.predecessors(node)) == sorted(rnx.predecessors(node))
        assert sorted(rfx.neighbors(node)) == sorted(rnx.neighbors(node))
        assert rfx.degree(node) == rnx.degree(node)
    assert rfx.has_edge("n3", "n0") == rnx.has_edge("n3", "n0")


@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
def test_reverse_view_is_still_frozen(cls_name):
    """br-r37-c1-rvfrz: mutating a reverse view must still raise, not no-op."""
    gnx, gfx = _build(nx, cls_name), _build(fnx, cls_name)
    for view in (gnx.reverse(copy=False), gfx.reverse(copy=False)):
        with pytest.raises(nx.NetworkXError):
            view.add_node("nope")


def test_a_subclass_gets_its_own_memo_entry():
    """The memo is keyed on the CLASS; a subclass must not inherit the answer."""

    class Sub(fnx.DiGraph):
        pass

    assert not fnx._class_shadows_nothing(Sub)

    class Shadowless(fnx.DiGraph):
        def has_node(self, n):
            return False

        def number_of_nodes(self):
            return 0

        def order(self):
            return 0

        def has_edge(self, u, v, key=None):
            return False

        def get_edge_data(self, u, v, default=None):
            return default

        def neighbors(self, n):
            return iter(())

        def successors(self, n):
            return iter(())

    assert fnx._class_shadows_nothing(Shadowless)
    assert not fnx._class_shadows_nothing(Sub), "memo leaked between subclasses"


def test_short_circuit_clears_a_stale_shadow_record_like_the_slow_path():
    """The early return must match the installer's own `else` branch.

    The slow path pops the shadow record when nothing was installed; the early
    return has to do the same or a stale record could survive.
    """
    view = _build(fnx, "DiGraph").reverse(copy=False)
    storage = vars(view)
    storage[fnx._PRIVATE_NODE_METHOD_SHADOWS] = {"has_node": None}
    fnx._install_private_method_shadows(view, storage)
    assert fnx._PRIVATE_NODE_METHOD_SHADOWS not in storage
