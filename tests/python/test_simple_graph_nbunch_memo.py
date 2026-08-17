"""``Graph.edges(nbunch, ...)`` — the last member of the nbunch memo family.

br-r37-c1-gnbmemo. Completes the sweep across br-r37-c1-mdginb (MultiDiGraph
in_edges), br-r37-c1-mgednb (MultiGraph edges) and br-r37-c1-dinbfam (the
directed family). A scan of 4 classes x {edges, in_edges, out_edges} x
{data=True, data=False, data=<key>} left simple ``Graph.edges`` as the only
member still unmemoized, at 0.6894x / 0.9319x / 0.9473x against networkx at
2000-character node keys.

THE PERFORMANCE NUMBER FOR THIS COMMIT IS NOT MEASURED. It was written during a
disk emergency (13G free, external build running) under an explicit
no-benchmarks instruction, so only correctness was verified. The before-figures
above are from the family scan in br-r37-c1-dinbfam; the after-figure is
deliberately absent rather than guessed, and this docstring should be updated
with a measured pair when a window permits.

TWO THINGS HERE ARE NOT LIKE THE OTHER FAMILY MEMBERS, and both are why this file
exists rather than a parametrize case bolted onto a sibling:

1. THIS PATH RETURNS THE NATIVE LIST DIRECTLY for ``data=True``. The other sites
   wrap their result in a view or rebuild it; this one has a standing comment
   justifying the direct return on the grounds that the list is "freshly built
   per call, so no aliasing". Memoizing invalidates that reasoning if the cached
   container itself is ever handed out. ``_nbunch_data_cache`` returns the
   native's own fresh list on a miss and a new ``list(...)`` over the cached
   tuple on a hit, so the caller never receives the cached container - but that
   is a property of the helper, not of this call site, so it is pinned here.

2. THE CACHE KEY CARRIES ``with_data``, NOT ``data``. The kernel takes a single
   boolean (``data is True or isinstance(data, str)``) and the three public
   shapes - ``data=False``, ``data=True``, ``data='attr'`` - are derived from one
   of two row shapes afterwards. So ``data=True`` and ``data='weight'`` SHARE a
   cache entry by design, and share it correctly, because they post-process the
   same rows differently. A test that only checked ``data=True`` twice would
   never exercise that.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

KEY_LEN = 40


def _build(lib, key_len: int = KEY_LEN, edges: int = 10):
    graph = lib.Graph()
    for i in range(edges):
        graph.add_edge(
            f"a{i}".ljust(key_len, "x"), f"b{i}".ljust(key_len, "y"), weight=i
        )
    graph.add_edge("a0".ljust(key_len, "x"), "a1".ljust(key_len, "x"), weight=99)
    graph.add_edge("a2".ljust(key_len, "x"), "a2".ljust(key_len, "x"), weight=7)  # self-loop
    return graph, list(graph.nodes())


def _norm(rows):
    out = []
    for row in rows:
        out.append(tuple(sorted(x.items()) if isinstance(x, dict) else x for x in row))
    return sorted(out, key=repr)


SPELLINGS = [
    ("data=True", dict(data=True)),
    ("data=False", dict(data=False)),
    ("data=weight", dict(data="weight")),
    ("data=weight,default", dict(data="weight", default=-1)),
    ("data=absent,default", dict(data="missing", default=-1)),
]
IDS = [s[0] for s in SPELLINGS]


@pytest.mark.parametrize("label,kw", SPELLINGS, ids=IDS)
def test_matches_networkx_twice(label, kw):
    got, nodes = _build(fnx)
    want, _ = _build(nx)
    nbunch = nodes[:6]
    for _ in range(2):
        assert _norm(got.edges(nbunch, **kw)) == _norm(want.edges(nbunch, **kw))


def test_shapes_sharing_one_entry_still_differ():
    """Point 2 — ``data=True`` and ``data='weight'`` share a cache entry.

    They are derived from the SAME cached rows, so this is the case where a
    post-processing mistake would surface as one shape answering for the other.
    Interleaved, and the no-attrs shape is mixed in because it uses the OTHER
    row shape and so must not collide with either.
    """
    got, nodes = _build(fnx)
    want, _ = _build(nx)
    nbunch = nodes[:6]
    for _ in range(3):
        for _label, kw in SPELLINGS:
            assert _norm(got.edges(nbunch, **kw)) == _norm(want.edges(nbunch, **kw))


def test_returned_list_is_never_the_cached_container():
    """Point 1 — the ``data=True`` branch hands its list straight to the caller."""
    got, nodes = _build(fnx)
    nbunch = nodes[:6]
    baseline = _norm(got.edges(nbunch, data=True))

    first = got.edges(nbunch, data=True)
    second = got.edges(nbunch, data=True)
    assert first is not second, "two calls returned the same list object"

    scratch = list(got.edges(nbunch, data=True))
    scratch.append(("poison", "poison", {}))
    del scratch[0]
    assert _norm(got.edges(nbunch, data=True)) == baseline


def test_attr_dicts_stay_live():
    got, nodes = _build(fnx)
    want, _ = _build(nx)
    nbunch = nodes[:6]
    got.edges(nbunch, data=True)
    want.edges(nbunch, data=True)
    for graph in (got, want):
        for _u, _v, attrs in list(graph.edges(nbunch, data=True)):
            attrs["live"] = 1
    assert _norm(got.edges(nbunch, data=True)) == _norm(want.edges(nbunch, data=True))
    assert all(d.get("live") == 1 for _u, _v, d in got.edges(nbunch, data=True))


def test_every_mutation_kind_invalidates():
    got, nodes = _build(fnx)
    want, _ = _build(nx)
    nbunch = nodes[:6]
    a0, b0 = nodes[0], nodes[1]

    def check(what):
        for _label, kw in SPELLINGS:
            assert _norm(got.edges(nbunch, **kw)) == _norm(
                want.edges(nbunch, **kw)
            ), f"stale after {what} ({kw})"

    check("warm")
    for g in (got, want):
        g[a0][b0]["weight"] = 4242
    check("attribute write through the adjacency view")
    for g in (got, want):
        g.add_edge("fresh".ljust(KEY_LEN, "z"), b0, weight=2)
    check("add edge from a new node")
    for g in (got, want):
        g.add_node("lonely".ljust(KEY_LEN, "q"))
    check("add isolated node")
    for g in (got, want):
        g.remove_edge(a0, b0)
    check("remove edge")
    for g in (got, want):
        g.remove_node(nodes[5])
    check("remove node")


def test_self_loops_and_repeated_nbunch_entries():
    """The fixture carries a self-loop; nx emits it once for a covering nbunch."""
    got, nodes = _build(fnx)
    want, _ = _build(nx)
    loop_node = "a2".ljust(KEY_LEN, "x")
    for nbunch in ([loop_node], [loop_node, loop_node], nodes[:6], nodes):
        for _label, kw in SPELLINGS:
            assert _norm(got.edges(nbunch, **kw)) == _norm(want.edges(nbunch, **kw))


def test_len_agrees_with_iteration():
    """``list(view)`` calls ``__len__`` first; it uses a SEPARATE count kernel."""
    got, nodes = _build(fnx)
    want, _ = _build(nx)
    for nbunch in ([], nodes[:1], nodes[:6], nodes, ["absent-node"]):
        view = got.edges(nbunch)
        assert len(view) == len(list(view))
        assert len(view) == len(want.edges(nbunch))


def test_different_nbunch_is_not_served_the_previous_one():
    got, nodes = _build(fnx)
    want, _ = _build(nx)
    for nbunch in (nodes[:3], nodes[3:6], [], nodes[:1], nodes[:6], nodes[2:5]):
        assert _norm(got.edges(nbunch, data=True)) == _norm(
            want.edges(nbunch, data=True)
        )


def test_non_primitive_nbunch_is_correct_though_unmemoized():
    got, nodes = _build(fnx)
    want, _ = _build(nx)
    for g in (got, want):
        g.add_edge((1, 2), (3, 4), weight=5)
    for nbunch in ([(1, 2)], {nodes[0], nodes[1]}):
        nb = list(nbunch) if isinstance(nbunch, set) else nbunch
        assert _norm(got.edges(nb, data=True)) == _norm(want.edges(nb, data=True))
