"""Standing guard: a request-scoped view operation must not read the WHOLE parent.

This pattern has bitten twice. br-r37-c1-thssf: DiGraph.subgraph(10
nodes).edges() built the whole parent adjacency and indexed ten rows out of it,
measured 0.0015x against networkx at N=32000 -- 667x slower -- because networkx
is O(rows asked for) and fnx was O(V+E). br-r37-c1-ymf62: the SIBLING branch of
the same routine, used by edge_subgraph() and restricted_view(), still did it,
at 0.0004x.

Both were found only when they happened to surface, and neither was caught by a
correctness test, because AT A SINGLE PARENT SIZE an O(V+E) read and an O(rows)
read return exactly the same answer. br-r37-c1-4jyoh then swept every view type
and found no third instance -- but a clean sweep is a statement about one
moment, and the next hoist that looks like a fix can reintroduce this silently.

SO THIS IS A CALL-COUNT ASSERTION, NOT A TIMING ONE. Counting is deterministic
and cheap; a timing assertion would be flaky on a shared host and would need a
big margin, which is exactly how a 2x regression slips through. The invariant is
structural and admits no margin: answering a question about a handful of rows
must not call a whole-graph accessor even once.

PROVEN NON-VACUOUS: run against the shim from before br-r37-c1-ymf62, this
counter reports `_native_adjacency_keys: 1` for DiGraph.edge_subgraph().edges().
Against HEAD it reports zero. `test_the_counter_can_actually_fire` keeps that
property honest in-process, so a future refactor that renames the accessors
turns this file red rather than quietly making it pass for free.

THE ASYMPTOTIC CAVEAT THIS FILE EXISTS TO PRESERVE. The subgraph row went from
0.0015x to 1.17-1.24x, which is a real fix -- but a RATIO is the thing that gets
quoted and the complexity is the thing that gets dropped. An O(V+E) hoist reads
like a fix and measures like one at the size it was checked at, while still
degrading without bound against an O(rows) incumbent. That is precisely what
br-cvsubedges did before br-r37-c1-thssf. A number cannot carry that caveat; a
test can.
"""

from __future__ import annotations

import random

import pytest

import franken_networkx as fnx

# Accessors that read the ENTIRE parent. Per-row accessors
# (_native_adjacency_row_dict, _native_successor_row_dict, _native_adjacency_row)
# are deliberately absent: reading one row to answer about one row is the fix,
# not the defect.
WHOLE_GRAPH_ACCESSORS = (
    "_native_adjacency_dict",
    "_native_adjacency_keys",
    "_native_edge_view_list",
)

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
N = 600


def _build(cls_name, seed=11):
    rng = random.Random(seed)
    graph = getattr(fnx, cls_name)()
    names = [f"n{i}" for i in range(N)]
    graph.add_nodes_from(names)
    for _ in range(N * 4):
        graph.add_edge(names[rng.randrange(N)], names[rng.randrange(N)], w=1)
    graph.add_edge(names[0], names[0], w=2)
    return graph, names


class _Counter:
    """Counts whole-graph accessor calls on the concrete graph classes."""

    def __init__(self):
        self.calls = {}
        self._saved = []

    def __enter__(self):
        for cls_name in CLASSES:
            cls = getattr(fnx, cls_name)
            for name in WHOLE_GRAPH_ACCESSORS:
                original = getattr(cls, name, None)
                if original is None:
                    continue
                self._saved.append((cls, name, original))

                def wrapper(self_, *args, _n=name, _o=original, _c=self.calls, **kw):
                    _c[_n] = _c.get(_n, 0) + 1
                    return _o(self_, *args, **kw)

                setattr(cls, name, wrapper)
        return self

    def __exit__(self, *exc):
        for cls, name, original in self._saved:
            setattr(cls, name, original)
        return False


def _requests(graph, names):
    rng = random.Random(7)
    pick = [names[rng.randrange(N)] for _ in range(5)]
    sub = graph.subgraph(pick)
    edges = [
        tuple(e)
        for e in (
            list(sub.edges(keys=True))[:3]
            if graph.is_multigraph()
            else list(sub.edges())[:3]
        )
    ]
    return pick, edges


# (label, builds a view, runs a request-scoped read on it)
CASES = [
    ("subgraph.edges", lambda g, p, e: list(g.subgraph(p).edges())),
    ("subgraph.edges(data)", lambda g, p, e: list(g.subgraph(p).edges(data=True))),
    ("subgraph.adj[u]", lambda g, p, e: [list(g.subgraph(p).adj[n]) for n in p[:2]]),
    ("subgraph.degree", lambda g, p, e: list(g.subgraph(p).degree())),
    ("subgraph.n_edges", lambda g, p, e: g.subgraph(p).number_of_edges()),
    ("edge_subgraph.edges", lambda g, p, e: list(g.edge_subgraph(e).edges())),
    ("edge_subgraph.edges(data)",
     lambda g, p, e: list(g.edge_subgraph(e).edges(data=True))),
    ("edge_subgraph.adj[u]",
     lambda g, p, e: [list(g.edge_subgraph(e).adj[n]) for n in g.edge_subgraph(e)][:2]),
    ("induced_subgraph.edges",
     lambda g, p, e: list(fnx.induced_subgraph(g, p).edges())),
    ("restricted_view.edges(nbunch)",
     lambda g, p, e: list(fnx.restricted_view(g, p[:2], []).edges(p[2:4]))),
    ("G.edges(nbunch)", lambda g, p, e: list(g.edges(p[:3]))),
    ("G.degree(nbunch)", lambda g, p, e: list(g.degree(p[:3]))),
    ("G.adj[u]", lambda g, p, e: [list(g.adj[n]) for n in p[:3]]),
    ("G.neighbors", lambda g, p, e: [list(g.neighbors(n)) for n in p[:3]]),
]


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("case", CASES, ids=[c[0] for c in CASES])
def test_request_scoped_read_does_not_touch_the_whole_parent(cls_name, case):
    label, run = case
    graph, names = _build(cls_name)
    pick, edges = _requests(graph, names)
    run(graph, pick, edges)  # warm any caches first; the assertion is about steady state
    with _Counter() as counter:
        run(graph, pick, edges)
    assert counter.calls == {}, (
        f"{cls_name}.{label} called whole-graph accessor(s) {counter.calls} to answer "
        "a request about a handful of rows -- this is the br-r37-c1-thssf / "
        "br-r37-c1-ymf62 defect returning"
    )


@pytest.mark.parametrize("cls_name", CLASSES)
def test_the_counter_can_actually_fire(cls_name):
    """Vacuity guard: the instrumentation must be able to observe a call.

    A guard that silently stopped patching anything -- because an accessor was
    renamed, or the classes stopped exposing it -- would pass forever and hide
    the very thing it exists to catch.
    """
    graph, _ = _build(cls_name)
    with _Counter() as counter:
        for name in WHOLE_GRAPH_ACCESSORS:
            accessor = getattr(graph, name, None)
            if accessor is None:
                continue
            # Signatures differ (_native_edge_view_list takes data/keys/default);
            # the point is only that SOME whole-graph accessor is observable.
            for args in ((), (False, False, None)):
                try:
                    accessor(*args)
                    break
                except TypeError:
                    continue
    assert counter.calls, (
        f"no whole-graph accessor on {cls_name} was patchable or callable; this "
        "guard is measuring nothing"
    )


def test_at_least_one_accessor_exists_on_every_class():
    """The names are the contract; a rename must fail here, loudly."""
    for cls_name in CLASSES:
        cls = getattr(fnx, cls_name)
        present = [n for n in WHOLE_GRAPH_ACCESSORS if hasattr(cls, n)]
        assert present, (
            f"{cls_name} exposes none of {WHOLE_GRAPH_ACCESSORS}; if these were "
            "renamed, update WHOLE_GRAPH_ACCESSORS or this whole file is inert"
        )
