"""``edges(data=True)`` must hand out the graph's LIVE attribute dicts.

br-r37-c1-ml7s5. Landed AHEAD of the fix, because it pins the property that fix
is most likely to break.

THE DEFECT being fixed: for a simple ``Graph``, ``edge_alldata_items`` probes the
``edge_py_attrs`` mirror with ``PyGraph::edge_key(left, right)``, which allocates
TWO owned Strings of full node-key length per edge purely to build a lookup key.
That is why the call grows with node-key length while the directed twin stays
flat — 114.9us at 3-character keys against 713.5us at 2000, where networkx is flat
at ~322us. The loop already holds the endpoint INDICES, and ``PyGraph`` already
carries an index-keyed lookaside (``edge_py_attrs_by_index``, br-r37-c1-ptiz2),
so the fix is to probe by index and fall back to the String key only on a miss.

WHY THIS TEST EXISTS. That change swaps which map answers the lookup, and the two
maps are only interchangeable if they hold the SAME dict objects. If the index
path ever returned a copy — or a freshly built dict on a miss it failed to also
record in the string-keyed mirror — then:

  * ``edges(data=True)`` would still return the right VALUES, so every equality
    assertion in the suite would pass, and
  * mutations through the returned dict would silently stop reaching the graph.

That is a silent wrong-answer bug behind a green test run, which is the failure
shape this campaign keeps finding. Identity and write-through are the only
assertions that catch it.

Verified against live networkx in the same test, so the contract is the
incumbent's rather than fnx's own habit. Both directions of write-through are
checked: through the yielded dict into the graph, and through the graph into a
dict yielded earlier.
"""

from __future__ import annotations

import pytest

import networkx as nx

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
# Straddle the 128-byte canonical stack buffer, which is where the borrowed and
# heap-spilled canonical paths diverge.
KEY_LENGTHS = [3, 130, 400]


def _build(lib, cls_name: str, key_len: int):
    graph = getattr(lib, cls_name)()
    nodes = [f"n{i}".ljust(key_len, "z") for i in range(6)]
    for i in range(5):
        graph.add_edge(nodes[i], nodes[i + 1], weight=i)
    return graph, nodes


def _pairs(graph, cls_name):
    """{(u, v): attr_dict} from edges(data=True), for any of the four classes."""
    return {(u, v): d for u, v, d in graph.edges(data=True)}


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("key_len", KEY_LENGTHS)
def test_yielded_dict_is_the_same_object_the_graph_serves(cls_name, key_len):
    """The dict from edges(data=True) IS the graph's, in both libraries."""
    for lib in (nx, fnx):
        graph, _nodes = _build(lib, cls_name, key_len)
        for (u, v), attrs in _pairs(graph, cls_name).items():
            served = graph[u][v] if not graph.is_multigraph() else graph[u][v][0]
            assert attrs is served, (
                f"{lib.__name__} {cls_name}: edges(data=True) yielded a COPY for "
                f"edge {u!r}-{v!r} at key length {key_len}, not the live dict"
            )


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("key_len", KEY_LENGTHS)
def test_write_through_the_yielded_dict_reaches_the_graph(cls_name, key_len):
    for lib in (nx, fnx):
        graph, _nodes = _build(lib, cls_name, key_len)
        pairs = _pairs(graph, cls_name)
        (u, v), attrs = next(iter(pairs.items()))
        attrs["written_through"] = 7
        served = graph[u][v] if not graph.is_multigraph() else graph[u][v][0]
        assert served["written_through"] == 7, (
            f"{lib.__name__} {cls_name}: a write through the yielded dict did not "
            f"reach the graph at key length {key_len}"
        )


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("key_len", KEY_LENGTHS)
def test_graph_side_write_is_visible_in_a_dict_yielded_earlier(cls_name, key_len):
    """The other direction: a dict handed out BEFORE the write must see it.

    An index-keyed cache that snapshotted attributes at materialisation time
    would pass the previous test — the object it handed out is still writable —
    and fail this one.
    """
    for lib in (nx, fnx):
        graph, _nodes = _build(lib, cls_name, key_len)
        pairs = _pairs(graph, cls_name)
        (u, v), attrs = next(iter(pairs.items()))
        if graph.is_multigraph():
            graph[u][v][0]["late"] = "value"
        else:
            graph[u][v]["late"] = "value"
        assert attrs["late"] == "value", (
            f"{lib.__name__} {cls_name}: a dict yielded before the write did not "
            f"see it at key length {key_len} — the view snapshotted"
        )


@pytest.mark.parametrize("cls_name", CLASSES)
def test_repeated_materialisation_yields_the_same_dicts(cls_name):
    """Two calls must hand out the SAME dict objects, not equal copies.

    The simple-Graph path caches its materialised tuples under
    ``(nodes_seq, edges_seq)``; a fix that rebuilt them, or that rebuilt only the
    attr dicts, would leave values equal and identity broken.
    """
    graph, _nodes = _build(fnx, cls_name, 130)
    first = _pairs(graph, cls_name)
    second = _pairs(graph, cls_name)
    assert first.keys() == second.keys()
    for pair in first:
        assert first[pair] is second[pair], (
            f"{cls_name}: repeated edges(data=True) yielded a different dict "
            f"object for {pair}"
        )


@pytest.mark.parametrize("cls_name", CLASSES)
def test_values_match_networkx(cls_name):
    """Guards the fixture: identity claims are meaningless if values diverge."""
    got, _ = _build(fnx, cls_name, 130)
    want, _ = _build(nx, cls_name, 130)
    assert sorted(
        (u, v, tuple(sorted(d.items()))) for u, v, d in got.edges(data=True)
    ) == sorted((u, v, tuple(sorted(d.items()))) for u, v, d in want.edges(data=True))
