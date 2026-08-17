"""A filtered ``edges(nbunch=...)`` must never be served the unfiltered list.

br-r37-c1-ml7s5. Landed ahead of the whole-list cache, and this is the hazard the
mutation guard does NOT cover.

THE NEXT LEVER is to give ``PyGraph`` the cache ``PyMultiGraph`` already has:
``_native_edge_view_list`` stores its materialised ``data=True`` tuples under
``(nodes_seq, edges_seq, keys)`` and returns ``clone_ref``s on a hit, while the
simple-graph path rebuilds every tuple on every call.

WHY THIS FILE. That cache is keyed on graph GENERATION, not on the request. But
``edges()`` and ``edges(nbunch=...)`` are different requests against the SAME
generation, and in the current code they are answered by two different branches —
``edge_alldata_items(py, &mut g, None)`` for the whole graph and
``edge_alldata_items(py, &mut g, Some(&node_set))`` for the filtered one. A cache
that stores under the generation alone, and is consulted from both branches,
serves whichever ran first:

  * warm the full list, then ask for a subset -> you get EVERY edge back, and
  * warm a subset, then ask for the full list -> you silently LOSE edges.

Both are wrong answers with the right types, and neither is caught by asserting
that a single call matches networkx, or by any mutation test: the generation
never moves, so every stamp is valid. Only asking the two questions in both
orders, against the same graph, exposes it.

The same trap has a precedent in this codebase — ``PyMultiGraph``'s cache
carries a ``keys`` flag in its key specifically because ``edges(data=True)`` and
``edges(keys=True, data=True)`` are different requests at one generation
(br-r37-c1-mgkd), and its comment records that the partial variants' apparent
wins were warm cache-hit artifacts. An nbunch filter is the same class of
discriminator and is not currently in any key.

Every expectation is taken from live networkx in the same test. Both orders are
run against a FRESH graph so neither can be contaminated by the other, and then
again against one shared graph, which is the case that actually fails.
"""

from __future__ import annotations

import pytest

import networkx as nx

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
KEY_LENGTHS = [3, 200]


def _build(lib, cls_name: str, key_len: int):
    graph = getattr(lib, cls_name)()
    nodes = [f"n{i}".ljust(key_len, "q") for i in range(6)]
    for i in range(5):
        graph.add_edge(nodes[i], nodes[i + 1], weight=i)
    return graph, nodes


def _snap(view):
    return sorted(
        (str(u), str(v), tuple(sorted(d.items()))) for u, v, d in view
    )


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("key_len", KEY_LENGTHS)
def test_subset_after_full_is_still_a_subset(cls_name, key_len):
    """Warm the FULL list, then ask for a subset. Must not get every edge."""
    for lib in (nx, fnx):
        graph, nodes = _build(lib, cls_name, key_len)
        full = _snap(graph.edges(data=True))
        subset = _snap(graph.edges(nodes[:2], data=True))
        assert len(subset) < len(full), (
            f"{lib.__name__} {cls_name} @{key_len}: edges(nbunch) returned "
            f"{len(subset)} edges after the full list was materialised, against "
            f"{len(full)} in the whole graph — the filtered request was served "
            "the unfiltered list"
        )


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("key_len", KEY_LENGTHS)
def test_full_after_subset_is_still_complete(cls_name, key_len):
    """The other order, and the more dangerous one: edges LOST, not gained."""
    for lib in (nx, fnx):
        graph, nodes = _build(lib, cls_name, key_len)
        graph.edges(nodes[:2], data=True)  # warm with a FILTERED request
        full = _snap(graph.edges(data=True))
        assert len(full) == graph.number_of_edges(), (
            f"{lib.__name__} {cls_name} @{key_len}: edges(data=True) returned "
            f"{len(full)} edges against number_of_edges()="
            f"{graph.number_of_edges()} after a filtered request was "
            "materialised first — edges were lost to a shared cache"
        )


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("key_len", KEY_LENGTHS)
def test_both_orders_match_networkx_on_one_shared_graph(cls_name, key_len):
    """The case that actually fails: both questions, one graph, both orders.

    A fresh graph per question hides a shared cache entirely, which is why the
    two tests above are not sufficient on their own.
    """
    fnx_graph, nodes = _build(fnx, cls_name, key_len)
    nx_graph, _ = _build(nx, cls_name, key_len)

    got_full_first = _snap(fnx_graph.edges(data=True))
    got_subset_second = _snap(fnx_graph.edges(nodes[:2], data=True))
    want_full = _snap(nx_graph.edges(data=True))
    want_subset = _snap(nx_graph.edges(nodes[:2], data=True))

    assert got_full_first == want_full
    assert got_subset_second == want_subset

    # ...and the reverse order on the same graphs, which must not drift.
    assert _snap(fnx_graph.edges(nodes[:2], data=True)) == want_subset
    assert _snap(fnx_graph.edges(data=True)) == want_full


@pytest.mark.parametrize("cls_name", CLASSES)
def test_two_different_nbunches_do_not_share_an_entry(cls_name):
    """Two filtered requests at one generation are also different requests."""
    fnx_graph, nodes = _build(fnx, cls_name, 200)
    nx_graph, _ = _build(nx, cls_name, 200)
    first = _snap(fnx_graph.edges(nodes[:2], data=True))
    second = _snap(fnx_graph.edges(nodes[3:], data=True))
    assert first == _snap(nx_graph.edges(nodes[:2], data=True))
    assert second == _snap(nx_graph.edges(nodes[3:], data=True))
    assert first != second, (
        f"{cls_name}: two different nbunch requests returned identical results, "
        "which means the second was served the first's entry"
    )
