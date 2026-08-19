"""br-r37-c1-hihrf — the emission order `G.edges(nbunch)` must keep.

WHY THIS FILE EXISTS, in one sentence: br-r37-c1-hihrf proposes replacing the
`edges(nbunch)` walk to make it O(sum of nbunch degrees) instead of O(E), the
bead names EMISSION ORDER as the one risk that change carries, and it asks for
the order to be pinned BEFORE the walk moves. Its consumer is whoever lands that
walk change; the gate it enforces is order parity with networkx; the observed
defect class is order divergence between a filtered global scan and an
adjacency-major walk. Delete it when `edges(nbunch)` no longer has two candidate
implementations.

WHAT THE MEASUREMENT SAID. Holding the nbunch fixed at 50 nodes and growing the
graph 8x (2000 -> 16000 nodes), the three edge spellings all scale together
(2.18x / 2.46x / 2.30x) while `degree(nbunch)` is flat at 0.99x and networkx is
flat at ~1.00x on everything — so the row crosses from 1.8034x of networkx to
0.8115x purely because the graph got bigger around a request that did not.

THE TRAP THIS FILE IS BUILT TO AVOID. A parity test that cannot tell the two
candidate orders apart passes no matter which walk runs, and would wave the
change through. So the fixtures are constructed so that

    filtered-global-scan order  !=  adjacency-major order

and `test_the_two_candidate_orders_actually_differ` asserts exactly that, per
fixture, as a precondition for the parity assertions being worth anything. On
the "interleaved" fixture the two orders are

    global scan      [('a','p'), ('a','t'), ('b','r'), ('b','u')]
    adjacency-major  [('b','r'), ('b','u'), ('a','p'), ('a','t')]

and both networkx and fnx emit the second.

WHAT THE PROBE FOUND, which is the useful half for the bead. fnx ALREADY emits
networkx's adjacency-major order — 448 comparisons per hash seed across four
classes, five fixtures, six nbunch permutations and every spelling, at
PYTHONHASHSEED 0/1/7/42, zero divergences. That is not luck: `G.edges(nbunch)`
is served by the Python `EdgeDataView`, whose `__iter__` walks adjacency rows
itself, and views.rs:1324 records that its native nbunch arm "is NOT what serves
`G.edges(nbunch)`". So the ordering risk the bead flags is smaller than it feared
— the target order is the order fnx already produces — and this file is what lets
the next person rely on that instead of re-deriving it.

Nothing here asserts a duration.
"""

from __future__ import annotations

import itertools
import os
import subprocess
import sys
from pathlib import Path

import networkx as nx
import pytest

REPO_PYTHON = Path(__file__).resolve().parents[2] / "python"
sys.path.insert(0, str(REPO_PYTHON))

import franken_networkx as fnx  # noqa: E402

CLASSES = ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph")

# Each fixture is (edges, nbunch). They are built so that walking every edge in
# insertion order and filtering by the nbunch produces a DIFFERENT sequence from
# walking the nbunch's adjacency rows in nbunch order.
FIXTURES = {
    # nbunch nodes' edges inserted far apart, with non-nbunch edges between them,
    # and the nbunch given in reverse of insertion order.
    "interleaved": (
        [("a", "p"), ("z", "q"), ("b", "r"), ("y", "s"), ("a", "t"), ("b", "u")],
        ["b", "a"],
    ),
    # every node is in the nbunch and the edges run between them, so the
    # skip-already-seen rule is what decides the order.
    "internal-edges": (
        [("a", "b"), ("c", "d"), ("b", "c"), ("a", "d"), ("d", "b"), ("a", "c")],
        ["d", "c", "b", "a"],
    ),
    # a node introduced early but edged late.
    "late-edges": (
        [("m", "n"), ("o", "p"), ("k", "m"), ("k", "o"), ("k", "p")],
        ["k", "m", "o"],
    ),
    # star whose centre is edged last.
    "star-last": (
        [("x1", "y1"), ("x2", "y2"), ("x3", "y3"), ("c", "x1"), ("c", "x2"), ("c", "x3")],
        ["c", "x2"],
    ),
    # self-loops and parallel edges, which the multigraph classes treat
    # differently from the simple ones.
    "loops-parallel": (
        [("a", "a"), ("a", "b"), ("b", "b"), ("a", "b"), ("c", "a"), ("b", "c")],
        ["b", "a"],
    ),
}


def _build(module, cls_name, edges):
    graph = getattr(module, cls_name)()
    for edge in edges:
        graph.add_edge(*edge, w=1)
    return graph


def _nbunches(nbunch):
    """The given order, its reverse, and every permutation of its first three."""
    out = [list(nbunch), list(reversed(nbunch))]
    out += [list(p) for p in itertools.permutations(nbunch[:3])]
    seen, unique = set(), []
    for nb in out:
        key = tuple(nb)
        if key not in seen:
            seen.add(key)
            unique.append(nb)
    return unique


def _spellings(cls_name):
    out = [
        ("edges(nb)", lambda g, nb: list(g.edges(nb))),
        ("edges(nb, data=True)", lambda g, nb: list(g.edges(nb, data=True))),
        ("edges(nb, data='w')", lambda g, nb: list(g.edges(nb, data="w", default=0))),
    ]
    if cls_name in ("DiGraph", "MultiDiGraph"):
        out += [
            ("out_edges(nb)", lambda g, nb: list(g.out_edges(nb))),
            ("in_edges(nb)", lambda g, nb: list(g.in_edges(nb))),
        ]
    if cls_name in ("MultiGraph", "MultiDiGraph"):
        out += [("edges(nb, keys=True)", lambda g, nb: list(g.edges(nb, keys=True)))]
    return out


# ---------------------------------------------------------------------------
# 0. the precondition that makes every assertion below discriminating
# ---------------------------------------------------------------------------
def _filtered_global_scan(graph, nbunch):
    """What a walk over ALL edges in insertion order, filtered, would emit.

    The predicate has to match what `edges(nbunch)` actually selects, or the two
    reference walks stop covering the same edges and the precondition fails for
    a reason that is not about order. On a DIRECTED graph `G.edges(nbunch)` is
    the OUT-edges of the nbunch, so an in-edge of an nbunch node is not in the
    answer; on an undirected graph either endpoint qualifies.
    """
    wanted = set(nbunch)
    if graph.is_directed():
        return [(u, v) for u, v in graph.edges() if u in wanted]
    return [(u, v) for u, v in graph.edges() if u in wanted or v in wanted]


def _adjacency_major(graph, nbunch):
    """What networkx's algorithm emits: nbunch-major, skipping seen nodes."""
    seen, out = set(), []
    for node in nbunch:
        for neighbour in graph.adj[node]:
            if neighbour not in seen:
                out.append((node, neighbour))
        seen.add(node)
    return out


def _pairs(sequence):
    """Endpoint-ORIENTATION-insensitive view of a sequence, order preserved.

    The two reference walks below disagree about which endpoint they name first
    on an undirected graph — `graph.edges()` uses the graph's own orientation
    while an adjacency-major walk names the nbunch node first. That is a
    different question from EMISSION ORDER, and conflating them would make the
    precondition below pass for the wrong reason.
    """
    return [tuple(sorted(pair[:2])) for pair in sequence]


@pytest.mark.parametrize("fixture_name", sorted(FIXTURES))
def test_the_two_candidate_orders_actually_differ(fixture_name):
    """If these ever coincide, every parity test in this file stops testing.

    br-r37-c1-hihrf's change swaps a filtered global scan for an adjacency-major
    walk. A fixture on which those two produce the SAME sequence cannot detect
    the swap, so asserting parity on it is a tautology dressed as a contract.
    This is the guard against that: it fails loudly if a fixture stops
    discriminating, rather than letting the file quietly become decorative.
    """
    edges, nbunch = FIXTURES[fixture_name]
    graph = _build(nx, "Graph", edges)
    scan = _pairs(_filtered_global_scan(graph, nbunch))
    adjacency = _pairs(_adjacency_major(graph, nbunch))
    assert sorted(scan) == sorted(adjacency), (
        "the two walks must cover the same edges — only their ORDER may differ"
    )
    assert scan != adjacency, (
        f"fixture {fixture_name!r} no longer distinguishes a filtered global "
        "scan from an adjacency-major walk, so the parity tests using it prove "
        "nothing — replace the fixture"
    )


@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph"])
@pytest.mark.parametrize("fixture_name", sorted(FIXTURES))
def test_a_global_scan_implementation_would_fail_this_file(cls_name, fixture_name):
    """The anti-tautology claim, asserted instead of argued.

    It is not enough that the two candidate orders differ in the abstract — the
    assertions in this file have to be the ones that notice. So take the output a
    filtered global scan WOULD produce and show it is not what fnx emits: any
    implementation that reverts to that walk fails
    `test_edges_nbunch_emission_order_matches_networkx` on this same fixture.

    Restricted to the simple classes because on a multigraph the two reference
    walks do not even cover the same multiset (one yields a tuple per parallel
    edge, the other one per neighbour), so they are not comparable as orders and
    the comparison would fail for a reason that has nothing to do with order.
    """
    edges, nbunch = FIXTURES[fixture_name]
    graph_nx = _build(nx, cls_name, edges)
    graph_fnx = _build(fnx, cls_name, edges)

    wrong = _pairs(_filtered_global_scan(graph_nx, nbunch))
    emitted = _pairs(graph_fnx.edges(nbunch))

    assert sorted(wrong) == sorted(emitted), (
        "same edges either way — this test is about order alone"
    )
    assert emitted != wrong, (
        f"{cls_name}/{fixture_name}: fnx emits the order a filtered global scan "
        "would, so this file cannot tell the two walks apart"
    )


@pytest.mark.parametrize("fixture_name", sorted(FIXTURES))
def test_networkx_itself_emits_the_adjacency_major_order(fixture_name):
    """The target is networkx's behaviour, so state what it is, from networkx."""
    edges, nbunch = FIXTURES[fixture_name]
    graph = _build(nx, "Graph", edges)
    emitted = _pairs(graph.edges(nbunch))
    assert emitted == _pairs(_adjacency_major(graph, nbunch))
    assert emitted != _pairs(_filtered_global_scan(graph, nbunch))


# ---------------------------------------------------------------------------
# 1. the pin itself
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("fixture_name", sorted(FIXTURES))
def test_edges_nbunch_emission_order_matches_networkx(cls_name, fixture_name):
    """Order parity for every class, nbunch permutation and spelling.

    This is the contract br-r37-c1-hihrf's walk change must not break. It is an
    ORDER assertion, not a set assertion — `sorted()` on either side would hide
    exactly the defect it is here to catch.
    """
    edges, nbunch = FIXTURES[fixture_name]
    graph_nx = _build(nx, cls_name, edges)
    graph_fnx = _build(fnx, cls_name, edges)

    for nb in _nbunches(nbunch):
        for label, call in _spellings(cls_name):
            expected = call(graph_nx, nb)
            got = call(graph_fnx, nb)
            assert got == expected, (
                f"{cls_name} / {fixture_name} / nbunch={nb} / {label}\n"
                f"  networkx: {expected}\n"
                f"  fnx     : {got}"
            )


@pytest.mark.parametrize("cls_name", CLASSES)
def test_single_node_and_empty_nbunch_order_matches_networkx(cls_name):
    """The degenerate nbunch shapes, which take different branches."""
    edges, _ = FIXTURES["interleaved"]
    graph_nx = _build(nx, cls_name, edges)
    graph_fnx = _build(fnx, cls_name, edges)
    for nb in ("a", "b", [], ["a"], iter(["b", "a"])):
        nb_nx = list(nb) if hasattr(nb, "__next__") else nb
        nb_fnx = list(nb_nx) if isinstance(nb_nx, list) else nb_nx
        assert list(graph_fnx.edges(nb_fnx)) == list(graph_nx.edges(nb_nx)), nb_nx


@pytest.mark.parametrize("cls_name", CLASSES)
def test_edges_nbunch_order_is_stable_across_repeated_iteration(cls_name):
    """A view is iterated more than once by design; the order must not drift.

    br-r37-c1-hihrf already records one bug of exactly this shape one level over
    — a materialised nbunch generator consumed by the FIRST iteration, leaving
    every later pass looking at an empty snapshot.
    """
    edges, nbunch = FIXTURES["internal-edges"]
    graph_nx = _build(nx, cls_name, edges)
    graph_fnx = _build(fnx, cls_name, edges)
    view_nx = graph_nx.edges(nbunch)
    view_fnx = graph_fnx.edges(nbunch)
    for _ in range(3):
        assert list(view_fnx) == list(view_nx)


# ---------------------------------------------------------------------------
# 2. hash seeds, because a set-derived order passes by luck on one seed
# ---------------------------------------------------------------------------
_SEED_CHILD = r"""
import itertools, sys
sys.path.insert(0, sys.argv[1])
import franken_networkx as fnx
import networkx as nx

FIXTURES = %(fixtures)r
CLASSES = %(classes)r

bad = total = 0
for cls in CLASSES:
    for edges, nbunch in FIXTURES.values():
        gn = getattr(nx, cls)()
        gf = getattr(fnx, cls)()
        for g in (gn, gf):
            for e in edges:
                g.add_edge(*e, w=1)
        order = [list(nbunch), list(reversed(nbunch))]
        order += [list(p) for p in itertools.permutations(nbunch[:3])]
        for nb in order:
            for call in (lambda g, nb: list(g.edges(nb)),
                         lambda g, nb: list(g.edges(nb, data=True))):
                total += 1
                if call(gn, nb) != call(gf, nb):
                    bad += 1
print(bad, total)
""" % {"fixtures": FIXTURES, "classes": CLASSES}


@pytest.mark.parametrize("hashseed", ["0", "1", "7", "42"])
def test_edges_nbunch_order_holds_under_several_hash_seeds(hashseed):
    """One seed proves nothing about an order that any set could be feeding.

    THE CHILD NEEDS PYTHONPATH EXPLICITLY. conftest puts the checkout on
    `sys.path` for the PARENT only, so a child that inherits just `os.environ`
    imports whatever `franken_networkx` is installed in site-packages — which on
    this host is thousands of lines behind the tree. That misreads as a wall of
    real order divergences; it cost a full shadow-tree gate run to diagnose. The
    interpreter path is passed as argv[1] rather than trusted to the environment.
    """
    env = {**os.environ, "PYTHONHASHSEED": hashseed}
    proc = subprocess.run(
        [sys.executable, "-c", _SEED_CHILD, str(REPO_PYTHON)],
        capture_output=True,
        text=True,
        env=env,
        timeout=300,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    bad, total = proc.stdout.split()
    assert int(total) > 0, "the child asserted nothing"
    assert int(bad) == 0, (
        f"{bad}/{total} nbunch edge-order divergences at PYTHONHASHSEED={hashseed}"
    )
