"""Which pure READS permanently disable the weighted-store fast path.

br-r37-c1-igdzi. This file pins a DEFECT, deliberately. The weighted-store fast
path behind ``size(weight=)`` and ``degree(weight=)`` is disabled for the LIFE OF
THE GRAPH by several ordinary reads, and the bead's own measurement puts the cost
at 4.395x -> 0.733x on ``Graph.size(weight)`` - a 6.0x self-regression on a graph
the caller never mutated.

WHY A TEST FOR A BUG. The fix needs a write barrier or a version counter on the
attr dicts, i.e. Rust and a build, and none is possible under the standing
freeze. Meanwhile the trigger set is the one thing that CAN be established
without a build, and it turned out to be much wider than the bead recorded. This
file is the baseline a fix will be measured against, and it stops the SAFE column
silently shrinking in the meantime - a new read that starts contaminating would
be a real regression today, invisible to every other test.

THE HEADLINE, and it is worse than the bead says. The bead bisected ten
operations and named ``edges(data=True)``. It never tried the two most common
edge reads in the library:

    G.neighbors(u)          CONTAMINATES - and merely CALLING it does, without
                            consuming the returned iterator at all
    G[u][v]                 CONTAMINATES
    G.get_edge_data(u, v)   CONTAMINATES
    G.edges[u, v]           CONTAMINATES
    G.adj[u][v]             CONTAMINATES
    list(G[u].items())      CONTAMINATES
    list(G.edges(data=True))CONTAMINATES

``neighbors`` is the single most common read there is - every traversal makes it -
so in practice the fast path is disabled almost immediately on any graph an
algorithm touches.

WHAT STAYS SAFE, which is the actionable half for callers today:

    G.edges()               safe
    G.edges(data="w")       safe   <- values, not dicts; use this over data=True
    G[u]  /  G.adj[u]       safe   <- taking the ROW is fine; iterating it is not
    G.nodes(data=True)      safe
    G.degree() / degree(weight=) / size(weight=) / has_edge()   safe

The pattern is exposure, not mutation: handing out an inner attr DICT (or an
iterator that reaches one) marks the store dirty, because the caller could write
through it. Returning values, or the row object itself, does not.

SCOPE, and this is a real limit rather than a hedge. Only ``Graph`` exposes a
dirty-gated kernel to Python (``_native_weighted_degree_int_values`` returns None
once dirty), so only ``Graph`` can be mapped without a build. The bead's timed
measurement shows the same collapse on all four classes after
``edges(data=True)``, so the defect is not Graph-only - but the per-operation
trigger set for the other three is UNVERIFIED and is not asserted here.
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx

CONTAMINATING = {
    "neighbors": lambda g: list(g.neighbors("n0")),
    "neighbors_uniterated": lambda g: g.neighbors("n0"),
    "getitem_edge": lambda g: g["n0"]["n1"],
    "adj_edge": lambda g: g.adj["n0"]["n1"],
    "get_edge_data": lambda g: g.get_edge_data("n0", "n1"),
    "edges_subscript": lambda g: g.edges[("n0", "n1")],
    "edges_data_true": lambda g: list(g.edges(data=True)),
    "row_items": lambda g: list(g["n0"].items()),
}

SAFE = {
    "edges": lambda g: list(g.edges()),
    "edges_data_key": lambda g: list(g.edges(data="w")),
    "edges_data_key_default": lambda g: list(g.edges(data="w", default=0)),
    "getitem_row": lambda g: g["n0"],
    "adj_row": lambda g: g.adj["n0"],
    "nodes_data": lambda g: list(g.nodes(data=True)),
    "degree": lambda g: dict(g.degree()),
    "degree_weighted": lambda g: dict(g.degree(weight="w")),
    "size_weighted": lambda g: g.size(weight="w"),
    "has_edge": lambda g: g.has_edge("n0", "n1"),
    "number_of_edges": lambda g: g.number_of_edges(),
}


def _graph(n=30):
    g = fnx.Graph()
    for i in range(n):
        g.add_edge("n%d" % i, "n%d" % ((i + 1) % n), w=i + 1)
    return g


def _store_fast_path_live(g):
    """True while the weighted-store fast path is still usable.

    The kernel returns None once the store is marked dirty, which is exactly the
    gate ``degree(weight=)`` and ``size(weight=)`` consult.
    """
    return g._native_weighted_degree_int_values("w") is not None


def test_a_fresh_graph_has_the_fast_path():
    assert _store_fast_path_live(_graph())


def test_probing_does_not_itself_contaminate():
    """Otherwise every row below would read CONTAMINATES for free."""
    g = _graph()
    assert _store_fast_path_live(g)
    assert _store_fast_path_live(g)
    assert _store_fast_path_live(g)


@pytest.mark.parametrize("label", sorted(SAFE))
def test_safe_reads_keep_the_fast_path(label):
    """The actionable half: these are what callers should prefer today."""
    g = _graph()
    assert _store_fast_path_live(g)
    SAFE[label](g)
    assert _store_fast_path_live(g), (
        f"{label} has STARTED contaminating the weighted store. That is a "
        "regression: it is on the safe list, and callers are told to prefer it."
    )


@pytest.mark.parametrize("label", sorted(CONTAMINATING))
def test_contaminating_reads_are_still_the_known_set(label):
    """Pins the DEFECT (br-r37-c1-igdzi), so a fix has an exact baseline.

    When the write barrier lands these assertions must be inverted deliberately,
    one line at a time - which is the point. A silent flip in either direction is
    a change in a documented, measured 6.0x behaviour.
    """
    g = _graph()
    assert _store_fast_path_live(g)
    CONTAMINATING[label](g)
    assert not _store_fast_path_live(g), (
        f"{label} no longer contaminates - if the write barrier landed, invert "
        "this case and update br-r37-c1-igdzi and the ledger row"
    )


def test_contamination_is_permanent():
    """Nothing recovers it, which is what makes the defect expensive."""
    g = _graph()
    list(g.neighbors("n0"))
    assert not _store_fast_path_live(g)
    g.add_edge("fresh_a", "fresh_b", w=1)
    assert not _store_fast_path_live(g)
    g.remove_edge("fresh_a", "fresh_b")
    assert not _store_fast_path_live(g)
    g.add_node("lonely")
    assert not _store_fast_path_live(g)
    # a brand new graph is the control: the defect is per-graph, not global
    assert _store_fast_path_live(_graph())


def test_the_weighted_answers_stay_correct_either_way():
    """The defect is PERFORMANCE only - parity must hold on both paths."""
    import networkx as nx

    clean, reference = _graph(), nx.Graph()
    for i in range(30):
        reference.add_edge("n%d" % i, "n%d" % ((i + 1) % 30), w=i + 1)

    before_size = clean.size(weight="w")
    before_degree = dict((str(k), v) for k, v in clean.degree(weight="w"))
    list(clean.neighbors("n0"))  # contaminate
    assert not _store_fast_path_live(clean)

    assert clean.size(weight="w") == before_size == reference.size(weight="w")
    after_degree = dict((str(k), v) for k, v in clean.degree(weight="w"))
    assert after_degree == before_degree
    assert after_degree == dict((str(k), v) for k, v in reference.degree(weight="w"))
