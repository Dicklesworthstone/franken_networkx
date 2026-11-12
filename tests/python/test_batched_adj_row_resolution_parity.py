"""br-r37-c1-8qxi9 — resolving a whole nbunch's rows with one preamble.

``_cached_adj_row_keydict`` re-does its warm-path preamble — ``vars()``, the two
revision reads, the token build and compare — on every call, and the nbunch edge
views called it once per node TWICE per ``edges(nbunch)``: once to build the
lazy walk and once to materialise. Profiled at nbunch=8 that was 16 calls at
about 1us each, and it was the dominant cost of the whole operation.

The preamble answers a question about the GRAPH, not about the row, so it is the
same answer for every node in a single call. ``_cached_adj_row_keydicts`` hoists
it and then reads the rows straight out of the cache, falling back to the
per-node function on any miss.

This is a pure fast path, so what needs locking is that it is INDISTINGUISHABLE
from the per-node loop it replaces — same rows, same objects, same order, on
cold caches, warm caches, stale tokens and graphs it must refuse. The batched
path returning a *different but plausible* row is the failure that timing would
never catch, and edges(nbunch) parity alone would only catch it where the two
happen to differ in content.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx


def _build(order=200):
    graph = fnx.Graph()
    for i in range(order):
        graph.add_edge(f"n{i}", f"n{(i * 7 + 3) % order}", weight=float(i % 5))
    graph.add_edge("n0", "n0")
    graph.add_node("isolated")
    return graph


def _per_node(graph, nodes):
    """Exactly the loop the batched helper replaced."""
    rows = []
    for node in nodes:
        row = fnx._cached_adj_row_keydict(graph, "adj", node, lambda: graph[node])
        if row is None:
            return None
        rows.append((node, row))
    return rows


NBUNCHES = [
    ["n0"],
    ["n0", "n1", "n2"],
    ["n5", "n5", "n5"],          # repeats
    ["isolated", "n0"],          # isolated node
    [f"n{i}" for i in range(40)],
]


@pytest.mark.parametrize("nbunch", NBUNCHES, ids=lambda b: f"{len(b)}nodes")
@pytest.mark.parametrize("warm", [False, True], ids=["cold", "warm"])
def test_batched_matches_the_per_node_loop_object_for_object(nbunch, warm):
    """Same nodes, same order, and the SAME row objects — not merely equal ones.

    The rows are live dicts that callers iterate; handing back a copy would
    silently break liveness while every content comparison still passed.
    """
    graph = _build()
    if warm:
        _per_node(graph, nbunch)
    batched = fnx._cached_adj_row_keydicts(
        graph, "adj", nbunch, lambda node: lambda: graph[node]
    )
    expected = _per_node(graph, nbunch)
    assert [n for n, _r in batched] == [n for n, _r in expected]
    for (_bn, brow), (_en, erow) in zip(batched, expected):
        assert brow is erow


def test_batched_refuses_exactly_where_the_per_node_loop_refuses():
    """A node with no resolvable row must give None from both, not a partial."""
    graph = _build()
    nbunch = ["n0", "n1"]
    assert fnx._cached_adj_row_keydicts(
        graph, "adj", nbunch, lambda node: lambda: graph[node]
    ) is not None
    missing = ["n0", "definitely-not-a-node"]
    batched_raises = per_node_raises = None
    try:
        batched = fnx._cached_adj_row_keydicts(
            graph, "adj", missing, lambda node: lambda: graph[node]
        )
    except Exception as exc:  # noqa: BLE001
        batched_raises = type(exc).__name__
        batched = None
    try:
        expected = _per_node(graph, missing)
    except Exception as exc:  # noqa: BLE001
        per_node_raises = type(exc).__name__
        expected = None
    assert batched_raises == per_node_raises
    assert batched == expected


def test_a_stale_token_is_not_served_from_the_warm_branch():
    """The hoisted token check must still invalidate.

    The whole risk of hoisting is doing it once and then trusting it too long.
    Warm the cache, mutate, and require the rows to reflect the mutation.
    """
    graph = _build()
    nbunch = ["n0", "n1", "n2"]
    fnx._cached_adj_row_keydicts(graph, "adj", nbunch, lambda n: lambda: graph[n])
    graph.add_edge("n0", "brand-new")
    rows = dict(
        fnx._cached_adj_row_keydicts(
            graph, "adj", nbunch, lambda node: lambda: graph[node]
        )
    )
    assert "brand-new" in rows["n0"]
    assert dict(_per_node(graph, nbunch))["n0"] == rows["n0"]


@pytest.mark.parametrize("order", [60, 600, 4000])
@pytest.mark.parametrize("size", [1, 4, 10, 40, 200])
@pytest.mark.parametrize("data", [False, True], ids=["nodata", "data"])
def test_edges_nbunch_still_matches_networkx_end_to_end(order, size, data):
    """The user-visible surface, across sizes that straddle the routing limit."""
    nbunch = [f"n{i}" for i in range(min(size, order))]
    gnx = nx.Graph()
    for i in range(order):
        gnx.add_edge(f"n{i}", f"n{(i * 7 + 3) % order}", weight=float(i % 5))
    gnx.add_edge("n0", "n0")
    gnx.add_node("isolated")
    gfx = _build(order)
    assert list(gfx.edges(nbunch, data=data)) == list(gnx.edges(nbunch, data=data))


def test_the_batched_helper_is_actually_on_the_edges_path():
    """Non-vacuity: if edges(nbunch) stops using it, these tests prove nothing."""
    graph = _build(4000)
    nbunch = [f"n{i}" for i in range(10)]
    calls = []
    original = fnx._cached_adj_row_keydicts

    def counting(*args, **kwargs):
        calls.append(args[2])
        return original(*args, **kwargs)

    fnx._cached_adj_row_keydicts = counting
    try:
        list(graph.edges(nbunch))
    finally:
        fnx._cached_adj_row_keydicts = original
    assert calls, "edges(nbunch) never reached the batched resolver"
