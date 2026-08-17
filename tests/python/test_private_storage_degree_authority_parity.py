"""br-r37-c1-vbe1o: the ASSIGNED degree view must key on the mapping, not the node view.

nx's DegreeView sets ``_nodes = self._succ`` -- which is ``_adj`` on an
undirected graph, and the successor side on a directed one even for the TOTAL
degree view. fnx's private-storage degree view iterated and measured
``self._graph``, the node view, so it dropped a node an assigned adjacency
carried and admitted one only an assigned ``_node`` carried. ``G.degree(n)`` also
returned a whole DegreeView where networkx returns an int -- a RETURN-TYPE
divergence, so arithmetic on the result raised TypeError rather than being wrong.

The class fixed here (``_AssignedPrivateDegreeView``) is instantiated ONLY for
graphs carrying private storage, so no ordinary graph reaches it and there is no
perf claim to make.

THE TWIN TRAP: ``_WeightAwareDegreeView`` looks like the right place and is not --
under private storage ``G.degree`` dispatches to ``_AssignedDegreeView``. Editing
the other one is a silent no-op, which is how the sibling has_edge fix went wrong
before a sweep caught it.
"""

import networkx as nx
import pytest

import franken_networkx as fnx

ADJ = {"a": {"b": {}}, "b": {"a": {}}, "ZZ": {"b": {}}}
SUCC = {"a": {"b": {}}, "b": {}, "ZZ": {"b": {}}}
NODE = {"a": {}, "b": {}, "ZZ": {}}
ALL = ["Graph", "MultiGraph", "DiGraph", "MultiDiGraph"]


def build(mod, cls, attr, mapping):
    g = getattr(mod, cls)()
    g.add_edge("a", "b")
    setattr(g, attr, dict(mapping))
    return g


def out(call):
    try:
        return ("ok", call())
    except Exception as exc:  # noqa: BLE001
        return (type(exc).__name__,)


@pytest.mark.parametrize("cls", ALL)
@pytest.mark.parametrize("attr,mapping", [("_adj", ADJ), ("_node", NODE)])
def test_degree_mapping_matches_networkx(cls, attr, mapping):
    expected = out(lambda: dict(build(nx, cls, attr, mapping).degree))
    got = out(lambda: dict(build(fnx, cls, attr, mapping).degree))
    assert got == expected


@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
def test_directed_total_degree_keys_on_the_successor_side(cls):
    """nx's DiDegreeView also uses _succ as `_nodes`, so an assigned _succ counts."""
    expected = out(lambda: dict(build(nx, cls, "_succ", SUCC).degree))
    got = out(lambda: dict(build(fnx, cls, "_succ", SUCC).degree))
    assert got == expected


@pytest.mark.parametrize("cls", ["Graph", "MultiGraph"])
def test_degree_of_a_node_only_in_assigned_adj_is_an_int(cls):
    """Undirected only: total degree needs just the one mapping."""
    expected = build(nx, cls, "_adj", ADJ).degree("ZZ")
    got = build(fnx, cls, "_adj", ADJ).degree("ZZ")
    assert isinstance(expected, int), "nx contract moved; update this file"
    assert isinstance(got, int), "returned a view where nx returns an int"
    assert got == expected


@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
def test_directed_total_degree_needs_both_sides(cls):
    """nx RAISES here, and matching that is the point.

    Total degree on a directed graph is ``len(_succ[n]) + len(_pred[n])``, so a
    node carried only by an assigned ``_adj``/``_succ`` has no ``_pred`` row and
    networkx raises KeyError. fnx must raise too rather than inventing a number
    -- this asserts the DIVERGENCE stays closed in the direction nx chose, not
    that an int comes back.
    """
    expected = out(lambda: build(nx, cls, "_adj", ADJ).degree("ZZ"))
    got = out(lambda: build(fnx, cls, "_adj", ADJ).degree("ZZ"))
    assert expected[0] == "KeyError", "nx contract moved; update this file"
    assert got == expected


@pytest.mark.parametrize("cls", ALL)
def test_len_of_the_degree_view_matches_networkx(cls):
    for attr, mapping in (("_adj", ADJ), ("_node", NODE)):
        expected = out(lambda: len(build(nx, cls, attr, mapping).degree))
        got = out(lambda: len(build(fnx, cls, attr, mapping).degree))
        assert got == expected, f"{cls} {attr}"


@pytest.mark.parametrize("cls", ALL)
def test_degree_over_an_nbunch_matches_networkx(cls):
    expected = out(lambda: dict(build(nx, cls, "_adj", ADJ).degree(["a", "ZZ"])))
    got = out(lambda: dict(build(fnx, cls, "_adj", ADJ).degree(["a", "ZZ"])))
    assert got == expected


@pytest.mark.parametrize("cls", ALL)
def test_ordinary_graphs_are_unchanged(cls):
    """Negative control: no assignment, so this view is never constructed."""
    gnx = getattr(nx, cls)()
    gfx = getattr(fnx, cls)()
    for g in (gnx, gfx):
        g.add_edge("a", "b")
        g.add_edge("b", "c")
        g.add_node("iso")
    assert dict(gfx.degree) == dict(gnx.degree)
    assert len(gfx.degree) == len(gnx.degree)
    for n in ("a", "b", "c", "iso"):
        assert gfx.degree(n) == gnx.degree(n)
    assert dict(gfx.degree(["a", "b"])) == dict(gnx.degree(["a", "b"]))


@pytest.mark.parametrize("cls", ALL)
def test_a_string_nbunch_is_one_node_not_its_characters(cls):
    """nx's nbunch_iter has TWO rules and the degree view must honour both.

    A SINGLE node -- tested with ``nbunch in self``, the node view -- yields
    ``[nbunch]``; anything else is filtered by ``n in self._adj``, the
    ADJACENCY. A plain ``for node in nbunch`` split a string into characters, so
    ``G.degree('ZZ')`` for a node carried only by an assigned ``_node`` produced
    an empty view where networkx produces a view over ``['ZZ']`` that raises on
    lookup.

    The list form is asserted alongside deliberately: it goes down the OTHER
    rule, and an earlier attempt that delegated to fnx's own ``nbunch_iter``
    fixed the string case while breaking this one -- fnx's version filters the
    second rule on the node view rather than the adjacency.
    """
    expected_str = out(lambda: dict(build(nx, cls, "_node", NODE).degree("ZZ")))
    got_str = out(lambda: dict(build(fnx, cls, "_node", NODE).degree("ZZ")))
    assert got_str == expected_str, "string nbunch"

    expected_list = out(lambda: dict(build(nx, cls, "_node", NODE).degree(["ZZ"])))
    got_list = out(lambda: dict(build(fnx, cls, "_node", NODE).degree(["ZZ"])))
    assert got_list == expected_list, "list nbunch"
    assert expected_str != expected_list, (
        "nx contract moved: the two nbunch rules no longer differ, so this test "
        "no longer pins what it was written to pin"
    )
