"""br-r37-c1-q32e6 — an unhashable key raises with networkx's WORDING, not just its type.

CPython 3.14 gives a container operation a longer `TypeError` than a bare
`hash()` does, and the wording names the container:

    d[k]      cannot use 'X' as a dict key (unhashable type: 'X')
    s.add(k)  cannot use 'X' as a set element (unhashable type: 'X')
    hash(k)   unhashable type: 'X'

networkx reaches every node and edge key through a real dict, so it always
produces the first. fnx PRE-CHECKS hashability — deliberately, to reproduce
networkx's ORDERING and its partial-graph state (br-r37-c1-baqyi,
br-r37-c1-n4c8l) — and a pre-check spelled `hash(k)` produced the third. A
76-cell sweep of the public spellings that can meet an unhashable key found 43
divergent against live networkx and ALL 43 differing on the message alone: same
exception type, same ordering, same partial state.

THE WORDING IS NOT WRITTEN DOWN ANYWHERE, in the product or in this file.
Hard-coding it pins fnx to one CPython version and it has already changed once.
The product probes a real dict (`_HASH_PROBE.get(k)` in the shim,
`hash_key_as_dict_would` in Rust) so the running interpreter supplies the text;
this file compares fnx against LIVE networkx for the same reason. Neither will
need editing when CPython changes it again.

WHY IT IS NOT COSMETIC HERE: an exception's message is part of the surface the
conformance suite compares, and `exception_sweep_must_compare_args` records that
type-only sweeps report false green — comparing `exc.args` is what exposed 48
divergences before. This is the same class, found the same way, and it was
holding 12 tests red across four files.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
DIRECTED = ["DiGraph", "MultiDiGraph"]
MULTI = ["MultiGraph", "MultiDiGraph"]


class Unhashable:
    """A node key that cannot be hashed, and says so in its repr."""

    __hash__ = None

    def __repr__(self):
        return "<Unhashable>"


UNHASHABLE_SHAPES = {
    "custom": Unhashable,
    "list": list,
    "dict": dict,
    "set": set,
    "bytearray": bytearray,
}


# br-r37-c1-c99d9 is FIXED, so nothing is excluded from the sweep any more. The
# entry that used to live here covered `G.subgraph([set()])`, which this sweep
# found and which turned out not to be a wording defect at all — a set-backed
# membership container cannot see an unhashable set, because CPython converts
# one to a frozenset for `x in aset`. Its own coverage is now in
# tests/python/test_subgraph_rejects_an_unhashable_nbunch_node.py.
KNOWN_GAPS: set[tuple[str, str]] = set()


def _pair(cls_name):
    graphs = []
    for lib in (nx, fnx):
        g = getattr(lib, cls_name)()
        g.add_edge("a", "b", weight=1.0)
        g.add_edge("b", "c", weight=2.0)
        graphs.append(g)
    return graphs


def _outcome(fn):
    try:
        return ("ok", repr(fn()))
    except Exception as exc:  # noqa: BLE001
        return ("exc", type(exc).__name__, str(exc))


def _spellings(g, cls_name, bad):
    table = {
        "G.edges[u,v]": lambda: g.edges[(bad(), "b")],
        "G.edges[a,v]": lambda: g.edges[("a", bad())],
        "G[u]": lambda: g[bad()],
        "G[a][v]": lambda: g["a"][bad()],
        "G.adj[u]": lambda: g.adj[bad()],
        "G.adj[a][v]": lambda: g.adj["a"][bad()],
        "G.nodes[u]": lambda: g.nodes[bad()],
        "G.degree[u]": lambda: g.degree[bad()],
        "G.add_edge(u,v)": lambda: g.copy().add_edge(bad(), "b"),
        "G.add_node(u)": lambda: g.copy().add_node(bad()),
        "G.has_edge(u,v)": lambda: g.has_edge(bad(), "b"),
        "G.get_edge_data(u,v)": lambda: g.get_edge_data(bad(), "b"),
        "G.neighbors(u)": lambda: list(g.neighbors(bad())),
        "G.remove_node(u)": lambda: g.copy().remove_node(bad()),
        "G.remove_edge(u,v)": lambda: g.copy().remove_edge(bad(), "b"),
        "G.nbunch_iter([u])": lambda: list(g.nbunch_iter([bad()])),
        "G.edges([u])": lambda: list(g.edges([bad()])),
        "G.degree([u])": lambda: list(g.degree([bad()])),
        "G.subgraph([u])": lambda: sorted(g.subgraph([bad()]).nodes(), key=repr),
    }
    if cls_name in DIRECTED:
        table["G.succ[u]"] = lambda: g.succ[bad()]
        table["G.pred[u]"] = lambda: g.pred[bad()]
        table["G.out_edges[u,v]"] = lambda: g.out_edges[(bad(), "b")]
        table["G.in_edges[u,v]"] = lambda: g.in_edges[(bad(), "b")]
    if cls_name in MULTI:
        table["G.add_edge(u,v,key)"] = lambda: g.copy().add_edge("a", "b", key=bad())
    return table


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("shape", sorted(UNHASHABLE_SHAPES))
def test_every_spelling_matches_networkx_exactly(cls_name, shape):
    """THE SWEEP. Value or (exception type AND message), compared cell by cell.

    Twelve of these were red at HEAD across test_unhashable_key_parity,
    test_edge_view_contains_spec, test_edge_view_slice_and_hash_order_parity and
    test_assigned_private_edge_view_getitem_parity, all with fnx producing the
    bare-hash wording where networkx produced the container's.
    """
    bad = UNHASHABLE_SHAPES[shape]
    gnx, gfx = _pair(cls_name)
    snx, sfx = _spellings(gnx, cls_name, bad), _spellings(gfx, cls_name, bad)
    for label in snx:
        if (label, shape) in KNOWN_GAPS:
            continue
        want, got = _outcome(snx[label]), _outcome(sfx[label])
        assert got == want, f"{cls_name} {label} with an unhashable {shape}"


@pytest.mark.parametrize("cls_name", CLASSES)
def test_a_hashable_key_is_untouched(cls_name):
    """The control: the probe must not change what a NORMAL key does.

    `_HASH_PROBE.get(k)` answers None for every hashable key and `hash(k)`
    answered an int; both are discarded, so nothing downstream can see the
    difference — asserted rather than assumed.
    """
    gnx, gfx = _pair(cls_name)
    snx, sfx = _spellings(gnx, cls_name, lambda: "a"), _spellings(
        gfx, cls_name, lambda: "a"
    )
    for label in snx:
        assert _outcome(sfx[label]) == _outcome(snx[label]), (cls_name, label)


def test_the_probe_is_an_empty_dict():
    """The mechanism, pinned.

    A dict is what makes the message right — a set or a bare `hash` produces
    different wording — and it must stay EMPTY so `.get` can never return
    something a caller might start relying on.
    """
    assert isinstance(fnx._HASH_PROBE, dict)
    assert fnx._HASH_PROBE == {}


def test_the_probe_reports_what_a_dict_reports():
    """No wording is written down here either — both sides are asked."""
    for shape, factory in UNHASHABLE_SHAPES.items():
        with pytest.raises(TypeError) as probe_err:
            fnx._HASH_PROBE.get(factory())
        with pytest.raises(TypeError) as dict_err:
            {}[factory()]
        assert str(probe_err.value) == str(dict_err.value), shape
        # And it is NOT the bare-hash wording, which is the whole point.
        with pytest.raises(TypeError) as hash_err:
            hash(factory())
        assert str(probe_err.value) != str(hash_err.value), shape


@pytest.mark.parametrize("cls_name", CLASSES)
def test_the_partial_graph_state_is_unchanged(cls_name):
    """The ordering contract the pre-checks exist for — br-r37-c1-baqyi.

    networkx creates node u BEFORE it examines v, so a bad v leaves u on the
    graph. Changing HOW the check reports a failure must not change WHEN it
    happens, and the observable is which nodes survive.
    """
    for bad in UNHASHABLE_SHAPES.values():
        gnx, gfx = _pair(cls_name)
        for graph in (gnx, gfx):
            with pytest.raises(TypeError):
                graph.add_edge("fresh-u", bad())
        assert sorted(gfx.nodes(), key=repr) == sorted(gnx.nodes(), key=repr), (
            cls_name,
            bad,
        )
